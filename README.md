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

### Check installed version
```
python3 -m pip show gisquick-cli | grep Version
```

## Setup deployment

Generate configuration for Gisquick deployment
```
gisquick-cli create <name>
```

This will create a deployment directory with generated main `docker-compose.yml` file,
environment variables files and configuration for core and selected optional services.
`gisquick-cli create` command allow to adjust configuration with selected predefined options.
For full control, you will have to modify configuration manually.

To see all Gisquick server options/environment variables, execute command:
```
docker run --rm gisquick/server gisquick serve --help
```

First start and initialization of the database
```
cd <name>
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

To see all Gisquick commands, run
```
docker compose exec app gisquick --help
```

## Logs and monitoring

Logs and monitoring data are accessible in Grafana web interface, available at `/admin/grafana` endpoint.
Initial user account is admin/admin (username/password)

### Setup of data sources

In `Configuration > Data sources` settings, add:
* Loki (http://loki:3100)
* Prometheus (http://prometheus:9090)


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

## Update

In most cases you can update Gisquick by fetching newer Docker images and recreating its containers

To update Gisquick services (server application and web applications), run
```
docker compose pull app web-map web-user
docker compose up -d app web-map web-user
```


## Useful commands

Generate new secret key
```
tr -dc 'a-z0-9!@#%^&*(-_=+)' < /dev/urandom | head -c50
```

Reload Caddy server
```
docker compose kill -s HUP caddy
```


## Gisquick running behind gateway server

It's easier when Gisquick is directly running on port 443 and managing it's SSL certificate.
However if you don't have that option, you can deploy Gisquick on different port and configure
reverse proxy on your gateway server. For most endpoints, simple reverse proxy is enough.
But if your gateway server doesn't handle websocket connections automatically, you will need to
adjust configuration. Also it's better to disable request buffering on project upload endpoint,
otherwise upload progressbar may not work correctly.

### Nginx

Example of Nginx configuration, assuming Gisquick is accessible on IP address 10.1.1.1 and port 80
```
location / {
    proxy_pass http://10.1.1.1;
}

location /ws/ {
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-NginX-Proxy true;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_pass http://10.1.1.1;
    proxy_redirect off;
    proxy_read_timeout 86400;

    # Websocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    # prevents 502 bad gateway error
    proxy_buffers 8 32k;
    proxy_buffer_size 64k;

    reset_timedout_connection on;
}

location /api/project/upload {
    client_max_body_size 500M;
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_intercept_errors on;
    proxy_request_buffering off;
    proxy_buffering off;
    proxy_http_version 1.1;
    chunked_transfer_encoding on;
    proxy_pass http://10.1.1.1;
}
```
