import logging
from typing import List, AnyStr, Any, Dict, Optional

from specklepy.api.client import SpeckleClient
from specklepy.api.resources.current.server_resource import ServerResource
from specklepy.core.api.models.graphql_base_model import GraphQLBaseModel
from specklepy.core.api.resource import ResourceBase
from gql import gql
from specklepy.core.api.responses import DataResponse
from .extended_model_resource import AutomateRunStatus, ExtendedModelResource

logger = logging.getLogger("Pipeline")
NAME = 'automation'


class AutomationRunObjectResult(GraphQLBaseModel):
    category: str
    message: Optional[str]
    metadata: Optional[Any]
    visualOverrides: Optional[Any]
    objectAppIds: Dict[str, str | None]


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

    def get(self, project_id: str, model_id: str, model_version_id: str,
            automation_id: Optional[str] = None) -> FunctionRunData:
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
                          if automation_id is None or a.automationId == automation_id)
        return next(run for run in automation.functionRuns if run.status == AutomateRunStatus.Succeeded)

    def try_get(self, project_id: str, model_id: str, model_version_id: str,
                automation_id: Optional[str] = None) -> Optional[FunctionRunData]:
        try:
            return self.get(project_id, model_id, model_version_id, automation_id)
        except Exception as e:
            logger.error(f"Failed to get automation [{project_id}, {model_id}, {model_version_id}, {automation_id}]", exc_info=e)
            return None

    @staticmethod
    def get_last_successful_automation(speckle_client: SpeckleClient,
                                       model_id: str,
                                       project_id: str,
                                       automation_id: Optional[str] = None) -> Optional[FunctionRunData]:
        model = ExtendedModelResource(speckle_client)
        model_data = model.get_with_versions(model_id,
                                             project_id, versions_limit=50)

        logger.info("; ".join([str(version) + " " +
                               str(version.automations_status and
                                   version.automations_status.status == AutomateRunStatus.Succeeded)
                               for version in model_data.versions.items]))

        success_version_id = None
        try:
            success_version_id = next(iter(version for version in sorted(model_data.versions.items,
                                                                         key=lambda x: x.created_at, reverse=True)
                                           if version.automations_status and
                                           version.automations_status.status == AutomateRunStatus.Succeeded)).id
            logger.info(f"Success version: {success_version_id}")
        except StopIteration:
            if model_data.versions.total_count > 50:
                logger.warning(f"Couldn't find a successful automation in the last 50 versions.")

        data = None
        if success_version_id is not None:
            logger.info(f"Getting automation for version {success_version_id}.")
            automation = AutomationResource(speckle_client)
            data = automation.try_get(project_id,
                                      model_id,
                                      success_version_id,
                                      automation_id)
        else:
            logger.info("No successful previous versions available.")
        return data
