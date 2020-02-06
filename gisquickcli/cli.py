#!/usr/bin/env python3

import os
import sys
import click
import shutil
import secrets
from ruamel.yaml import YAML
from ruamel.yaml.tokens import CommentToken
from ruamel.yaml.error import CommentMark
from ruamel.yaml.comments import CommentedSeq, CommentedMap

yaml=YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.default_flow_style = False

BASE_DIR = os.path.dirname(__file__)
service_keys_order = ["restart", "image", "volumes", "environment", "env_file", "expose", "ports", "logging", "command"]


def fatal(msg):
    click.secho(msg, fg="red", err=True)
    sys.exit(1)


# https://stackoverflow.com/questions/42172399/modifying-yaml-using-ruamel-yaml-adds-extra-new-lines
# https://stackoverflow.com/questions/42198379/how-can-i-add-a-blank-line-before-some-data-using-ruamel-yaml
def remove_ending_newline(obj):
    last_key = list(obj.keys())[-1]
    if last_key in obj.ca.items and obj.ca.items[last_key][2].value.endswith("\n\n"):
        obj.ca.items.pop(last_key)
        return True
    if hasattr(obj[last_key], "ca"):
        last_item_index = len(obj[last_key]) - 1
        last_item_ca = obj[last_key].ca.items.get(last_item_index)
        if last_item_ca and last_item_ca[0].value.endswith("\n\n"):
            obj[last_key].ca.items[last_item_index][0] = None
            obj[last_key].ca.items.pop(last_item_index)
            return True
    return False

def add_ending_newline(obj):
    last_key = list(obj.keys())[-1]
    if type(obj[last_key]) == list:
        obj[last_key] = CommentedSeq(obj[last_key])
    if hasattr(obj[last_key], "ca"):
        ct = CommentToken("\n\n", CommentMark(0), None)
        index = len(obj[last_key]) - 1
        obj[last_key].ca.items[index] = [ct, None, None, None]
    else:
        ct = CommentToken("\n\n", CommentMark(0), None)
        obj.ca.items[last_key] = [None, None, ct, None]


def get_random_string(length=50, chars="abcdefghijklmnopqrstuvwxyz0123456789!@#%^&*(-_=+)"):
    return "".join(secrets.choice(chars) for i in range(length))


def create_env_file(path, vars, overwrite=False):
    if not os.path.exists(path) or overwrite:
        with open(path, "w") as f:
            f.write("\n".join(["{0}={1}".format(k, v) for k, v in vars.items()]))
            f.write("\n")


def create_symlink(src, dest):
    if os.path.exists(dest):
        if not os.path.islink(dest):
            fatal("Only symlinks is allowed to replace: %s" % dest)
        os.unlink(dest)
    os.symlink(src, dest)


class KeyedList:
    def __init__(self, obj, separator):
        self.list = obj
        self.separator = separator

    def index_of(self, key):
        for index, item in enumerate(self.list):
            k = item.split(self.separator)[0]
            if k == key:
                return index
        return -1

    def remove(self, key, must_exist=False):
        key_index = self.index_of(key)
        if key_index != -1:
            del self.list[key_index]
        elif must_exist:
            raise KeyError(key)
        return self

    def replace(self, key, value):
        key_index = self.index_of(key)
        if key_index != -1:
            self.list[key_index] = value
        return self

    def append(self, value):
        self.list.append(value)
        return self

    def update(self, *values):
        for value in values:
            key = value.split(self.separator)[0]
            key_index = self.index_of(key)
            if key_index != -1:
                self.list[key_index] = value
            else:
                self.list.append(value)
        return self


class VolumesList(KeyedList):
    def __init__(self, obj):
        super().__init__(obj, separator=":")

class EnvVars(KeyedList):
    def __init__(self, obj):
        super().__init__(obj, separator="=")


##### Configs #####

def local_profile(config, context):
    services = config["services"]

    def map_ports(service):
        ports = service.pop("expose")
        service["ports"] = ["{0}:{0}".format(port) for port in ports]

    map_ports(services["postgres"])
    map_ports(services["qgisserver"])
    map_ports(services["django"])
    map_ports(services["go"])

    services["nginx"]["ports"] = ["80:80"]


def django_dev_config(config, context):
    services = config["services"]

    django_conf = services["django"]
    VolumesList(django_conf["volumes"])\
        .remove("assets")\
        .append(CommentedMap(
            type='bind',
            source='${GISQUICK_DJANGO_REPO}/server/webgis',
            target='/gisquick/server/webgis'
        ))

    EnvVars(django_conf["environment"]).update(
        "DJANGO_STATIC_ROOT=/var/www/gisquick/static/",
        "DJANGO_DEBUG=True",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONUNBUFFERED=1"
    )
    django_conf["command"] = "django-admin runserver 0.0.0.0:8000"


def go_dev_config(config, context):
    services = config["services"]
    go_conf = services["go"]
    go_conf["image"] = "gisquick/settings-dev"
    go_conf["volumes"].extend([
        CommentedMap(type='bind', source='${GISQUICK_SETTINGS_REPO}/go/src', target='/go/src'),
        CommentedMap(type='bind', source='${GISQUICK_SETTINGS_REPO}/go/cmd', target='/go/cmd')
    ])


def sqlite_config(config, context):
    services = config["services"]
    services.pop("postgres")
    EnvVars(services["django"]["environment"])\
        .update("GISQUICK_SQLITE_DB=/var/www/gisquick/data/gisquick.sqlite3")


def postgres_config(config, context):
    services = config["services"]
    services["django"]["env_file"].append("postgres.env")
    create_env_file(os.path.join(context["output_dir"], "postgres.env"), {
        "POSTGRES_DB": "gisquick",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": get_random_string(8)
    })


def nginx_common(config, context):
    src = os.path.join(context["template_dir"], "nginx", "error")
    dest = os.path.join(context["output_dir"], "nginx", "error")
    if not os.path.exists(dest):
        shutil.copytree(src, dest)


def nginx_local(config, context):
    nginx_common(config, context)

    services = config["services"]
    nginx_conf = services["nginx"]
    VolumesList(nginx_conf["volumes"])\
        .remove("certbot")\
        .remove("letsencrypt")\
        .replace("./nginx/conf/", "./nginx/conf.local/:/etc/nginx/conf.d/")

    nginx_conf["ports"] = ["80:80"]

    volumes = config["volumes"]
    volumes.pop("certbot")
    volumes.pop("letsencrypt")

    src_dir = os.path.join(context["template_dir"], "nginx", "conf")
    dest_dir = os.path.join(context["output_dir"], "nginx", "conf.local")
    files = ["conf.local", "locations", "proxy-parameters"]
    os.makedirs(dest_dir, exist_ok=True)
    for filename in files:
        src = os.path.join(src_dir, filename)
        dest = os.path.join(dest_dir, filename)
        shutil.copy(src, dest)
    os.rename(os.path.join(dest_dir, "conf.local"), os.path.join(dest_dir, "default.conf"))


def letsencrypt_profile(config, context):
    if not context.get("server_name"):
        context["server_name"] = click.prompt("\nEnter server name")

    nginx_common(config, context)
    exclude = ["conf.local"]
    src_dir = os.path.join(context["template_dir"], "nginx", "conf")
    dest_dir = os.path.join(context["output_dir"], "nginx", "conf.letsencrypt")
    os.makedirs(dest_dir, exist_ok=True)
    for filename in os.listdir(src_dir):
        if filename in exclude:
            continue
        src = os.path.join(src_dir, filename)
        dest = os.path.join(dest_dir, filename)
        with open(src) as f:
            conf = f.read().replace("${NGINX_HOST}", context["server_name"])
            with open(dest, "w") as outfile:
                outfile.write(conf)

    create_symlink("conf.letsencrypt", os.path.join(dest_dir, "default.conf"))
    VolumesList(config["services"]["nginx"]["volumes"])\
        .replace("./nginx/conf/", "./nginx/conf.letsencrypt/:/etc/nginx/conf.d/")

    shutil.copy(os.path.join(context["template_dir"], "certbot.yaml"), os.path.join(context["output_dir"], "certbot.yaml"))


def no_accounts(config, context):
    services = config["services"]
    services.pop("web-accounts")
    EnvVars(services["django"]["environment"])\
        .update("GISQUICK_ACCOUNTS_ENABLED=False")


@click.group()
def cli():
    """CLI for generating Gisquick deploymets"""
    pass


@cli.command()
@click.argument("name")
def create(name):
    """Create a new deployment environment"""
    click.secho("Creating a new deployment environment in directory: %s" % name, fg="cyan")

    if os.path.exists(name):
        fatal("Directory already exists: %s" % os.path.abspath(name))
    os.mkdir(name)

    # with open(os.path.join(name, ".gitignore"), "w") as f:
    #     f.write("# Ignore everything in this directory\n*")

    create_env_file(os.path.join(name, ".env"), {
        "SECRET_KEY": get_random_string()
    })
    click.secho('Created ".env" file for global settings', fg="yellow")
    create_env_file(os.path.join(name, "django.env"), {})
    click.secho('Created "django.env" file', fg="yellow")

    os.makedirs(os.path.join(name, "data", "publish"))
    click.secho('Created "data/publish" folder for published projects', fg="yellow")


@cli.command()
@click.option("--name", "compose_name", help="Compose name. Profile name will be used as default.")
@click.option("--profile", type=click.Choice(["local", "letsencrypt"]), default="local")
@click.option("--db", type=click.Choice(["sqlite", "postgres"]), default="sqlite")
@click.option("--django-dev", is_flag=True, default=False, help="Configure django service for development")
@click.option("--go-dev", is_flag=True, default=False, help="Configure go service for development")
@click.option('--accounts', is_flag=True, default=False, help="Include web app for users registration.")
@click.option('--server-name', help="Server name used in nginx configuration.")
def compose(compose_name, profile, db, django_dev, go_dev, accounts, server_name):
    """Generate docker compose configuration by entered options"""

    context = {
        "output_dir": "",
        "template_dir": os.path.join(BASE_DIR, "template"),
        "server_name": server_name
    }

    compose_filename = os.path.join(context["template_dir"], "docker-compose.yml")
    with open(compose_filename) as file:
        config = yaml.load(file)

    # remove ending newline from last key of each service (if found)
    striped_newlines = {}
    for service_name, service in config["services"].items():
        striped_newlines[service_name] = remove_ending_newline(service)


    click.secho("Generating docker compose configuration...", fg="cyan")
    click.secho("profile: %s" % profile, fg="yellow")
    click.secho("db: %s" % db, fg="yellow")
    click.secho("accounts extension: %s" % ("Yes" if accounts else "No"), fg="yellow")

    if profile == "local":
        local_profile(config, context)
        nginx_local(config, context)
    else:
        letsencrypt_profile(config, context)

    if db == "sqlite":
        sqlite_config(config, context)
    else:
        postgres_config(config, context)

    if django_dev:
        django_dev_config(config, context)

    if go_dev:
        go_dev_config(config, context)

    if not accounts:
        no_accounts(config, context)

    # Adjust final config for pretty output

    # Sort keys in services
    services = config["services"]
    for service_name, service in services.items():
        # data = CommentedMap()
        data = {}
        for k in service_keys_order:
            if k in service:
                data[k] = service.pop(k)
        services[service_name].update(data)

    # add newline at the (new) end, if it was removed before
    for service_name, service in config["services"].items():
        if striped_newlines.get(service_name, False):
            add_ending_newline(service)


    suffix_name = profile
    if django_dev or go_dev:
        suffix_name += ".dev"
    dest_file = "docker-compose.%s.yml" % (compose_name or suffix_name)
    with open(dest_file, "w") as file:
        file.write("# Generated with: gisquick-cli %s\n\n" % " ".join(sys.argv[1:]))
        yaml.dump(config, file)

    click.secho("Docker Compose file saved as: %s" % dest_file, fg="cyan")


    django_conf_dir = os.path.join(context["output_dir"], "django")
    if not os.path.exists(django_conf_dir):
        src = os.path.join(context["template_dir"], "django")
        click.secho("Generating Django configuration: %s" % django_conf_dir, fg="cyan")
        shutil.copytree(src, django_conf_dir)


@cli.command()
@click.argument("compose_filename")
def use(compose_filename):
    """Set selected docker compose file as default"""
    if not os.path.exists(compose_filename):
        fatal("Compose file does not exists: %s" % compose_filename)
    create_symlink(compose_filename, "docker-compose.yml")


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        # raise # For development
        fatal(str(e))
