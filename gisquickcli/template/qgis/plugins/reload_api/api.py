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

    # def path(self):
    #     return QRegularExpression("/reload") # not working in/since 3.22
    #     return QRegularExpression("/") # works in 3.16 and 3.22

    def operationId(self):
        return "ReloadApi"

    def summary(self):
        return "Removes project entry from config cache"

    def description(self):
        return "Removes project entry from config cache"

    def linkTitle(self):
        return "Projects config cache reloader"

    def linkType(self):
        return QgsServerOgcApi.data

    def handleRequest(self, context):
        """ """

        values = self.values(context)
        project = values['MAP']
        self.serverIface.removeConfigCacheEntry(project)
        data = {
            "project": project
        }
        self.write(data, context)

    def parameters(self, context):
        return [QgsServerQueryStringParameter('MAP', True, QgsServerQueryStringParameter.Type.String, 'Project path')]


class ReloadApi():

    def __init__(self, serverIface):
        api = QgsServerOgcApi(serverIface, '/reload',
                            'reload api', 'a reload api', '1.0')
        reload_handler = ReloadApiHandler(serverIface)
        api.registerHandler(reload_handler)
        serverIface.serviceRegistry().registerApi(api)
