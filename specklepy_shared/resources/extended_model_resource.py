from datetime import datetime
from enum import Enum
from typing import Optional

from gql import gql
from specklepy.api.client import SpeckleClient
from specklepy.api.resources.current.model_resource import ModelResource
from specklepy.core.api.inputs import ModelVersionsFilter
from specklepy.core.api.models import ModelWithVersions, LimitedUser, ResourceCollection, Model
from specklepy.core.api.models.graphql_base_model import GraphQLBaseModel
from specklepy.core.api.responses import DataResponse


class AutomateRunStatus(Enum):
    Pending = 'PENDING'
    Initializing = 'INITIALIZING'
    Running = 'RUNNING'
    Succeeded = 'SUCCEEDED'
    Failed = 'FAILED'
    Exception = 'EXCEPTION'
    Timeout = 'TIMEOUT'
    Canceled = 'CANCELED'


class TriggeredAutomationsStatus(GraphQLBaseModel):
    status: AutomateRunStatus


class ExtendedVersion(GraphQLBaseModel):
    author_user: Optional[LimitedUser]
    created_at: datetime
    id: str
    message: Optional[str]
    preview_url: str
    referenced_object: Optional[str]
    """Maybe null if workspaces version history limit has been exceeded"""
    source_application: Optional[str]
    automations_status: Optional[TriggeredAutomationsStatus]

    def __str__(self):
        return f"Version {self.id} [{self.created_at}, {self.automations_status}]"


class ModelWithExtendedVersions(Model):
    versions: ResourceCollection[ExtendedVersion]


class ExtendedModelResource(ModelResource):
    def __init__(self, client: SpeckleClient):
        super().__init__(
           account=client.account,
           basepath=client.url,
           client=client.httpclient,
           server_version=client.server.server_version
        )

    def get_with_versions(
        self,
        model_id: str,
        project_id: str,
        *,
        versions_limit: int = 25,
        versions_cursor: Optional[str] = None,
        versions_filter: Optional[ModelVersionsFilter] = None,
    ) -> ModelWithExtendedVersions:
        QUERY = gql(
            """
            query ModelGetWithVersions(
              $modelId: String!,
              $projectId: String!,
              $versionsLimit: Int!,
              $versionsCursor: String,
              $versionsFilter: ModelVersionsFilter
              ) {
              data:project(id: $projectId) {
                data:model(id: $modelId) {
                  id
                  name
                  previewUrl
                  updatedAt
                  versions(
                    limit: $versionsLimit,
                    cursor: $versionsCursor,
                    filter: $versionsFilter
                    ) {
                    items {
                      id
                      referencedObject
                      message
                      sourceApplication
                      createdAt
                      previewUrl
                      authorUser {
                        avatar
                        id
                        name
                        bio
                        company
                        verified
                        role
                      }
                      automationsStatus {
                        status
                      }
                    }
                    totalCount
                    cursor
                  }
                  description
                  displayName
                  createdAt
                  author {
                    avatar
                    bio
                    company
                    id
                    name
                    role
                    verified
                  }
                }
              }
            }
            """
        )

        variables = {
            "projectId": project_id,
            "modelId": model_id,
            "versionsLimit": versions_limit,
            "versionsCursor": versions_cursor,
            "versionsFilter": (
                versions_filter.model_dump(warnings="error", by_alias=True)
                if versions_filter
                else None
            ),
        }

        return self.make_request_and_parse_response(
            DataResponse[DataResponse[ModelWithExtendedVersions]], QUERY, variables
        ).data.data
