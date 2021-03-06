# #######
# Copyright (c) 2016-2020 Cloudify Platform Ltd. All rights reserved
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
"""
    resources.network.NetworkSecurityGroup
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Microsoft Azure Network Security Group interface
"""

# Node properties and logger
from cloudify import ctx
# Base resource class
from cloudify_azure.resources.base import Resource
# Lifecycle operation decorator
from cloudify.decorators import operation
# Logger, API version
from cloudify_azure import (constants, utils)


class NetworkSecurityGroup(Resource):
    """
        Microsoft Azure Network Security Group interface

    .. warning::
        This interface should only be instantiated from
        within a Cloudify Lifecycle Operation

    :param string resource_group: Name of the parent Resource Group
    :param string api_version: API version to use for all requests
    :param `logging.Logger` logger:
        Parent logger for the class to use. Defaults to `ctx.logger`
    """
    def __init__(self,
                 resource_group=None,
                 api_version=constants.API_VER_NETWORK,
                 logger=None,
                 _ctx=ctx):
        resource_group = resource_group or \
            utils.get_resource_group(_ctx=_ctx)
        Resource.__init__(
            self,
            'Network Security Group',
            '/{0}/{1}'.format(
                'resourceGroups/{0}'.format(resource_group),
                'providers/Microsoft.Network/networkSecurityGroups'
            ),
            api_version=api_version,
            logger=logger,
            _ctx=_ctx)


@operation(resumable=True)
def create(**_):
    """Uses an existing, or creates a new, Network Security Group"""
    # Create a resource (if necessary)
    utils.task_resource_create(
        NetworkSecurityGroup(api_version=ctx.node.properties.get(
            'api_version', constants.API_VER_NETWORK)),
        {
            'location': ctx.node.properties.get('location'),
            'tags': ctx.node.properties.get('tags'),
            'properties': utils.get_resource_config()
        })


@operation(resumable=True)
def delete(**_):
    """Deletes a Network Security Group"""
    # Delete the resource
    utils.task_resource_delete(
        NetworkSecurityGroup(api_version=ctx.node.properties.get(
            'api_version', constants.API_VER_NETWORK)))
