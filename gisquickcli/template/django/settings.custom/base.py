DEBUG = False

ADMINS = [('admin', 'admin@gisquick.org')]
GISQUICK_PROJECT_ROOT = '/publish/'
GISQUICK_MAPSERVER_URL = 'http://qgisserver:90/cgi-bin/qgis_mapserv.fcgi'

GISQUICK_ACCOUNTS_ENABLED = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True
        },
        'gisquick': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True
        }
    }
}

