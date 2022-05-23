import os
import json

from qgis.PyQt.QtCore import QRegularExpression
from qgis.server import (
    QgsServerOgcApi,
    QgsServerQueryStringParameter,
    QgsServerOgcApiHandler
)

# from qgis.core import (
#     QgsMessageLog
# )


class ReloadApiHandler(QgsServerOgcApiHandler):

    def __init__(self, serverIface):
        super(ReloadApiHandler, self).__init__()
        self.serverIface = serverIface
        self.setContentTypes([QgsServerOgcApi.JSON])

    def path(self):
        return QRegularExpression("/reload")

    def operationId(self):
        return "ReloadApi"

    def summary(self):
        return "TODO: summary"

    def description(self):
        return "TODO: description"

    def linkTitle(self):
        return "TODO: linkTitle"

    def linkType(self):
        return QgsServerOgcApi.data

    def handleRequest(self, context):
        """ """

        values = self.values(context)
        project = values['project']
        self.serverIface.removeConfigCacheEntry(project)
        data = {
            "project": project
        }
        self.write(data, context)

    def parameters(self, context):
        return [QgsServerQueryStringParameter('project', True, QgsServerQueryStringParameter.Type.String, 'Project')]


class ReloadApi():

    def __init__(self, serverIface):
        api = QgsServerOgcApi(serverIface, '/reload',
                            'reload api', 'a reload api', '1.0')
        reload_handler = ReloadApiHandler(serverIface)
        api.registerHandler(reload_handler)
        serverIface.serviceRegistry().registerApi(api)