import logging
from typing import List, AnyStr, Any, Dict, Optional

from specklepy.api.client import SpeckleClient
from specklepy.api.resources.current.server_resource import ServerResource
from specklepy.core.api.models.graphql_base_model import GraphQLBaseModel
from specklepy.core.api.resource import ResourceBase
from gql import gql
from specklepy.core.api.responses import DataResponse
from extended_model_resource import AutomateRunStatus

logger = logging.getLogger("Pipeline")
NAME = 'automation'


class AutomationRunObjectResult(GraphQLBaseModel):
    category: str
    message: Optional[str]
    metadata: Optional[Any]
    visualOverrides: Optional[Any]
    objectAppIds: Dict[str, str]


class FunctionRunDataResultValue(GraphQLBaseModel):
    objectResults: List[AutomationRunObjectResult]
    blobIds: List[Any]


class FunctionRunDataResult(GraphQLBaseModel):
    version: int
    values: FunctionRunDataResultValue


class FunctionRunData(GraphQLBaseModel):
    results: Optional[FunctionRunDataResult]
    status: AutomateRunStatus


class AutomationRunData(GraphQLBaseModel):
    functionRuns: List[FunctionRunData]
    automationId: str


class AutomationDataProjectModelStatus(GraphQLBaseModel):
    automationRuns: List[AutomationRunData]


class AutomationDataProjectModelVersion(GraphQLBaseModel):
    automationsStatus: Optional[AutomationDataProjectModelStatus]


class AutomationDataProjectModel(GraphQLBaseModel):
    version: AutomationDataProjectModelVersion


class AutomationDataProject(GraphQLBaseModel):
    model: AutomationDataProjectModel


class AutomationData(GraphQLBaseModel):
    project: AutomationDataProject


class AutomationResource(ResourceBase):
    def __init__(self, client: SpeckleClient) -> None:
        super().__init__(
            account=client.account,
            basepath=client.url,
            client=client.httpclient,
            name=NAME,
            server_version=client.server.server_version,
        )

    def get(self, project_id: str, model_id: str, automation_id: str, model_version_id: str) -> FunctionRunData:
        query = gql("""
                        query AutomationData($modelId: String!, $projectId: String!, $versionId: String!) {
                          project(id: $projectId) {
                            model(id: $modelId) {
                              version(id: $versionId) {
                                automationsStatus {
                                  automationRuns {
                                    functionRuns {
                                      results
                                      status
                                    }
                                    automationId
                                    automation {
                                      id
                                    }
                                  }
                                }
                              }
                            }
                          }
                        }
                        """)

        variables = {"modelId": model_id, "projectId": project_id, "versionId": model_version_id}
        data = self.make_request_and_parse_response(
            AutomationData, query, variables
        )
        automation = next(a for a in data.project.model.version.automationsStatus.automationRuns
                          if a.automationId == automation_id)
        return next(run for run in automation.functionRuns if run.status == AutomateRunStatus.Succeeded)

    def try_get(self, project_id: str, model_id: str, automation_id: str, model_version_id: str) -> Optional[FunctionRunData]:
        try:
            return self.get(project_id, model_id, automation_id, model_version_id)
        except Exception as e:
            logger.error(e)
            return None

