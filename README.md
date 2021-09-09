
## Gisquick CLI

Set of commands to simplify and speed up setup of new deployment(s).

### Installation:

```
pip3 install git+https://github.com/gisquick/gisquick-cli
```
or without `git` already installed
```
pip3 install https://github.com/gisquick/gisquick-cli/archive/master.zip
```

### Commands

Create a new empty deployment environment. One environment can contain several docker compose files (different variations of deployment), which will share all global volumes (publish, assets, media, db, ...)
```
gisquick-cli create <name>
```
Created files:

- .env - default values for any environment variables referenced in the Compose file, or used to configure Compose. See [Compose Reference](https://docs.docker.com/compose/environment-variables/).
- django.env - environment variables for *django* service
- data/publish - root folder for published projects

Create docker compose file with specified options
```
gisquick-cli compose [OPTIONS]
```

Set specified docker compose file as default
```
gisquick-cli use <compose-file>
```

## Local deployment

If you already doesn't have one, create a new deployment environment
```
gisquick-cli create gisquick
cd gisquick
```

Create and set docker compose file. Run ```gisquick-cli compose --help``` to see all options (database, ...)
```
gisquick-cli compose --profile=local
gisquick-cli use docker-compose.local.yml
```

Before first start of Gisquick, adjust its [configuration](#startup-configuration)


Start all services
```
docker-compose up
```

After creating a new deployment, you will have to [initialize DB](#db-initialization)

Gisquick will be running on: [http://localhost](http://localhost)


## Django development deployment

This configuration run Gisquick django server in development mode with source files mounted from host machine.

Create docker compose file
```
gisquick-cli compose --name=django-dev --django-dev
gisquick-cli use docker-compose.django-dev.yml
```

Fetch repository with source files
```
git clone https://github.com/gisquick/gisquick.git
```

Set path to django server source repository - ```GISQUICK_DJANGO_REPO``` in ```.env``` file

```
docker-compose up
```

See also [Local deployment](#local-deployment) for information about initial configuration and DB initialization.


## Go development deployment

Create docker compose file
```
gisquick-cli compose --name=go-dev --go-dev
gisquick-cli use docker-compose.go-dev.yml
```

Fetch repository with source files
```
git clone https://github.com/gisquick/gisquick-settings.git
```

Build image required for development
```
docker build -f Dockerfile.dev -t gisquick/settings-dev .
```

Set path to go server source repository - ```GISQUICK_SETTINGS_REPO``` in ```.env``` file

```
docker-compose up
```

After you made changes in source files, restart service to recompile:
```
docker-compose restart go
```

See also [Local deployment](#local-deployment) for information about initial configuration and DB initialization.


## Https localhost deployment

If you already doesn't have one, create a new deployment environment
```
gisquick-cli create gisquick
cd gisquick
```

Create and set docker compose file. Template for letsencrypt deployment will be suitable also for openssl self-signed certificate.
```
export SERVER_NAME=localhost
gisquick-cli compose --profile=letsencrypt --server-name=$SERVER_NAME
gisquick-cli use docker-compose.letsencrypt.yml
```

Create self-signed certificate and generate nginx configuration
```
mkdir ssl

openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout ssl/privkey.pem \
    -out ssl/fullchain.pem \
    -subj "/C=CZ/ST=State/L=City/O=Gisquick/OU=IT Department/CN=$SERVER_NAME"

docker-compose run --rm -v $(pwd)/ssl:/tmp/ssl -e SERVER_NAME=$SERVER_NAME nginx bash -c 'mkdir -p /etc/letsencrypt/live/$SERVER_NAME && cp /tmp/ssl/* /etc/letsencrypt/live/$SERVER_NAME/'
```

It's also necessary to delete or comment configuration of `ssl_trusted_certificate` parameter in `nginx/conf.letsencrypt/ssl-parameters` file for this kind of certificate.

Before first start of Gisquick, adjust its [configuration](#startup-configuration)

```
docker-compose up
```

After creating a new deployment, you will have to [initialize DB](#db-initialization)

Gisquick will be running on: [https://localhost](https://localhost)


## Server deployment with Let's Encrypt certificate

If you already doesn't have one, create a new deployment environment
```
gisquick-cli create gisquick
cd gisquick
```

Create and set docker compose file.
```
export SERVER_NAME=example.com
gisquick-cli compose --profile=letsencrypt --server-name=$SERVER_NAME
gisquick-cli use docker-compose.letsencrypt.yml
```

Before first start of Gisquick, adjust its [configuration](#startup-configuration)

Temporary switch to configuration with http protocol only
```
rm nginx/conf.letsencrypt/default.conf
ln -s conf.http nginx/conf.letsencrypt/default.conf
```

Start Gisquick
```
docker-compose up -d
```

Create Let's Encrypt certificate
```
docker-compose -f certbot.yml run --rm certbot certonly --agree-tos -a webroot \
    --webroot-path /var/www/certbot/ \
    --email admin@gisquick.org \
    -d $SERVER_NAME
```

Switch to normal configuration and restart nginx server
```
rm nginx/conf.letsencrypt/default.conf
ln -s conf.letsencrypt nginx/conf.letsencrypt/default.conf
docker-compose restart nginx
```

Now should be Gisquick working over https protocol. Before you start using it, you will have to [initialize DB](#db-initialization) first.

Renew certificate before it will expire:
```
docker-compose -f certbot.yml run --rm certbot renew
docker-compose kill -s HUP nginx
```

Tip: use `--dry-run` option in certbot commands for testing


## Startup configuration

### Django configuration

You can extend default Gisquick Django configuration in ```django/settings.custom/``` directory.


When using optional *accounts* extension (```GISQUICK_ACCOUNTS_ENABLED=True```), you need to setup correct email configuration:
- Check/adjust ```<settings-directory>/email.py```
- Set variables ```DJANGO_EMAIL_HOST_USER``` and ```DJANGO_EMAIL_HOST_PASSWORD``` in ```django.env``` (or in ```<settings-directory>/email.py```) 


## DB initialization

Create database (django service must be running)
```
docker-compose exec django django-admin makemigrations app
docker-compose exec django django-admin migrate
```

Create superuser account
```
docker-compose exec django django-admin createsuperuser
```

Create regular users from admin interface running on <server-url>/admin


## Useful commands

Generate new secret key
```
tr -dc 'a-z0-9!@#%^&*(-_=+)' < /dev/urandom | head -c50
```

Reload NGINX server
```
docker-compose kill -s HUP nginx
```

Update web app
```
docker-compose up -d web-map
```
Note: use ```--force-recreate``` flag to update assets even if image didn't change

## Notes

### Define upload & project limits

Upload file size limit is defined in `docker-compose.yml`:

```
MAX_FILE_UPLOAD=50M
```

Project size limit is defined by two files: `docker-compose.yml`

```
MAX_PROJECT_SIZE=150M
```

and `nginx/conf.letsencrypt/locations`

```
client_max_body_size 150M;
```

### Change user password from shell

Enter django container.

```bash
docker-compose exec django django-admin shell
```

Execute statements below.

```py
from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(username='myuser')
u.set_password('mypassword')
u.save()
```
