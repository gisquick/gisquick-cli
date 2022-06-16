## Requirements

docker, docker compose, python3 with pip

### Install Docker
Follow instructions on https://docs.docker.com/engine/install/


### Install Docker Compose
Follow instructions on https://docs.docker.com/compose/install/compose-plugin/


Or download and install specific version
```
mkdir -p ~/.docker/cli-plugins/
curl -SL https://github.com/docker/compose/releases/download/v2.5.1/docker-compose-linux-x86_64 -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose
```

### Install Python3 + pip

For Ubuntu distribution
```
apt-get update
apt-get install -y --no-install-recommends python3 python3-setuptools python3-pip
```


## Gisquick CLI

Set of commands to simplify and speed up setup of new deployment(s).

### Installation:

```
python3 -m pip install  https://github.com/gisquick/gisquick-cli/archive/master.zip
```

For development, install from source code
```
python3 -m pip install -e <path-to-gisquick-cli>
```

## Setup deployment
```
gisquick-cli create gisquick

cd gisquick

docker compose up -d

gisquick-cli migrate up

```

## Create user/superuser account
```
docker compose exec app sh
gisquick adduser
```
or
```
gisquick addsuperuser
```

## Logs and monitoring

Logs and monitoring data are accessible in Grafana web interface, available at `/admin/grafana` endpoint.
Initial user account is admin/admin (username/password)

TODO: setup of data sources


## Deployment for server development

Build development version of server's Docker image (see README of its source code)

Use `--dev-server` flag for generating deployment files
```
gisquick-cli create --dev-server gisquick
```

After you made changes in source files, restart service to recompile:
```
docker-compose restart app
```

## Notes

### Define project size limit

Project size limit is defined by `GISQUICK_MAX_PROJECT_SIZE` environment variable in `docker-compose.yml`



## Useful commands

Generate new secret key
```
tr -dc 'a-z0-9!@#%^&*(-_=+)' < /dev/urandom | head -c50
```

Reload Caddy server
```
docker compose kill -s HUP caddy
```

Update web app
```
docker compose up -d web-map
```
Note: use ```--force-recreate``` flag to update assets even if image didn't change
