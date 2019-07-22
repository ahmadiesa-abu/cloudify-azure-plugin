# #######
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ast
import json

from cloudify import exceptions as cfy_exc
from cloudify.decorators import operation

from cloudify_azure import constants

from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import DeploymentMode

from cloudify_azure.auth.oauth2 import to_service_principle_credentials


class Deployment(object):

    def __init__(self,
                 logger,
                 credentials,
                 resource_group,
                 deployment_name=None,
                 timeout=None):

        self.resource_group = resource_group
        self.deployment_name = deployment_name or resource_group
        self.logger = logger
        self.timeout = timeout or 900
        self.resource_verify = bool(credentials.get('endpoint_verify', True))
        self.credentials = to_service_principle_credentials(
            client_id=str(credentials['client_id']),
            certificate=str(credentials.get('certificate', '')),
            thumbprint=str(credentials.get('thumbprint', '')),
            cloud_environment=str(credentials.get('cloud_environment', '')),
            secret=str(credentials.get('client_secret', '')),
            tenant=str(credentials['tenant_id']),
            verify=self.resource_verify,
            endpoints_active_directory=str(credentials.get(
                'endpoints_active_directory', '')),
            resource=str(credentials.get('endpoint_resource',
                                         constants.OAUTH2_MGMT_RESOURCE),)
        )
        self.client = ResourceManagementClient(
            self.credentials, str(credentials['subscription_id']),
            base_url=str(credentials.get('endpoints_resource_manager',
                                         constants.CONN_API_ENDPOINT)))

        self.logger.info("Use subscription: {0}"
                         .format(credentials['subscription_id']))

    def create(self, location):
        """Deploy the template to a resource group."""
        self.logger.info("Create resource group...")
        self.client.resource_groups.create_or_update(
            self.resource_group,
            {
                "location": location
            },
            verify=self.resource_verify
        )

    def get(self):
        return self.client.deployments.get(
            self.resource_group,  # resource group name
            self.deployment_name,  # deployment name
        )

    @staticmethod
    def format_params(params):
        # We need to traverse the parameters' dictionary
        # and convert all unicode strings to regular strings
        def convert_value(v):
            if v is None:
                return None
            if isinstance(v, int) or isinstance(v, bool) or isinstance(v, str):
                return v
            if isinstance(v, unicode):
                return ast.literal_eval(repr(v))
            if isinstance(v, dict):
                for k, y in v.items():
                    v[k] = convert_value(y)
                return v
            raise Exception("Unhandled data type: {} ({})".format(
                type(v), str(v)))

        if params is None:
            return None
        for k, v in params.items():
            updated_value = convert_value(v)
            params[k] = {"value": updated_value}
        return params

    def update(self, template, params):

        self.logger.info("Create deployment...")

        deployment_properties = {
            'mode': DeploymentMode.incremental,
            'template': template,
            'parameters': self.format_params(params)
        }

        deployment_async_operation = self.client.deployments.create_or_update(
            self.resource_group,  # resource group name
            self.resource_group,  # deployment name
            deployment_properties,
            verify=self.resource_verify
        )
        self.logger.info("Wait deployment...Timeout: {0}"
                         .format(repr(self.timeout)))
        deployment_async_operation.wait(timeout=self.timeout)

    def delete(self):
        """Destroy the given resource group"""
        self.logger.info("Delete resource groups...")
        deployment_async_operation = self.client.resource_groups.delete(
            self.resource_group,
            verify=self.resource_verify
        )
        self.logger.info("Wait delete deployment...Timeout: {0}"
                         .format(repr(self.timeout)))
        deployment_async_operation.wait(timeout=self.timeout)


@operation
def create(ctx, **kwargs):
    properties = {}
    properties.update(ctx.node.properties)
    properties.update(kwargs)

    ctx.logger.info("Create: {0}".format(repr(properties['name'])))

    deployment = Deployment(ctx.logger, properties['azure_config'],
                            properties['name'],
                            timeout=properties.get('timeout'))

    if ctx.node.properties.get('use_external_resource', False):
        ctx.logger.info("Using external resource")
    else:
        # load template
        template = properties.get('template')
        if not template and properties.get('template_file'):
            ctx.logger.info("Using {0} as template"
                            .format(repr(properties['template_file'])))
            template = ctx.get_resource(properties['template_file'])
            template = json.loads(template)

        if not template:
            raise cfy_exc.NonRecoverableError(
                "A deployment template is not defined.")

        # create deployment
        deployment.create(location=properties['location'])
        ctx.instance.runtime_properties['resource_id'] = properties['name']

        # update deployment
        deployment.update(template=template,
                          params=properties.get('params', {}))

    resource = deployment.get()
    ctx.instance.runtime_properties['outputs'] = resource.properties.outputs


@operation
def delete(ctx, **kwargs):
    if ctx.node.properties.get('use_external_resource', False):
        return
    properties = {}
    properties.update(ctx.node.properties)
    properties.update(kwargs)
    ctx.logger.info("Delete: {0}".format(
        repr(ctx.instance.runtime_properties['resource_id'])
    ))
    deployment = Deployment(ctx.logger, properties['azure_config'],
                            ctx.instance.runtime_properties['resource_id'],
                            timeout=properties.get('timeout'))
    deployment.delete()
