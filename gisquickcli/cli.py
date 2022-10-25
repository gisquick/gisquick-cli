#!/usr/bin/env python3

import os
import re
import sys
import click
import shutil
import string
import secrets
from urllib.parse import urlsplit, quote
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


def generate_password(length):
    chars = string.ascii_letters + string.digits + string.punctuation
    safe_char = secrets.choice(string.ascii_letters + string.digits)
    return safe_char + "".join(secrets.choice(chars) for i in range(length - 1))

def quote_string(val):
    escaped = re.sub("[^\\\]'", lambda m: m.group(0)[0] + "\\'", val)
    return "'" + escaped + "'"

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


def subst_file(path, data):
    with open(path) as f:
        fdata = f.read()
        for param, val in data.items():
            fdata = fdata.replace("${%s}" % param, "%s" % val)
    with open(path, "w") as outfile:
        outfile.write(fdata)


##### Configs #####

def app_server_config(config, context):
    EnvVars(config["services"]["app"]["environment"])\
        .update("GISQUICK_SIGNUP_API=%s" % context["accounts"])
        # .update("WEB_SITE_URL=%s" % context["server_url"])


def server_dev_config(config, context):
    services = config["services"]
    go_conf = services["app"]
    go_conf["image"] = "gisquick/server-dev"
    go_conf["volumes"].append(
        CommentedMap(type='bind', source=context["server_src"], target='/go/server'),
        # CommentedMap(type='bind', source='${GISQUICK_SERVER_REPO}', target='/go/server'),
    )


def caddy_config(config, context):
    serv_url = urlsplit(context["server_url"])
    server_name = serv_url.netloc
    if serv_url.hostname == "localhost":
        server_name = ":%s" % (serv_url.port or 80)
    if serv_url.port:
        ports = [port]
    elif serv_url.scheme == "http":
        ports = [80]
    else:
        ports = [80, 443]

    if serv_url.scheme == "https" and serv_url.port:
        click.secho("When using non-standard port with https scheme, you will need to configure ssl certificates", fg="orange")

    service = config["services"]["caddy"]
    for port in ports:
        service["ports"].append("{0}:{0}".format(port))

    src = os.path.join(context["template_dir"], "caddy")
    dest = os.path.join(context["output_dir"], "caddy")
    if not os.path.exists(dest):
        shutil.copytree(src, dest)
    subst_file(os.path.join(dest, "Caddyfile"), {"SERVER_NAME": server_name})


def prometheus_config(config, context):
    if not context["node_exporter"] or not context["cadvisor"]:
        conf_filename = os.path.join(context["output_dir"], "prometheus", "prometheus.yml")
        with open(conf_filename) as file:
            config = yaml.load(file)
            scrape_configs = config["scrape_configs"]
            def job_index(name):
                for i, job in enumerate(scrape_configs):
                    if job["job_name"] == name:
                        return i
                return -1

            if not context["node_exporter"]:
                scrape_configs.pop(job_index("node"))
            if not context["cadvisor"]:
                scrape_configs.pop(job_index("cadvisor"))

        with open(conf_filename, "w") as file:
            yaml.dump(config, file)


@click.group()
def cli():
    """CLI for generating Gisquick deploymets"""
    pass


def validate_server_url(ctx, param, value):
    try:
        url = urlsplit(value)
        if url.scheme != "http" and url.scheme != "https":
            raise ValueError(value)
    except ValueError as e:
            click.echo('Invalid URL: {}'.format(e))
            value = click.prompt(param.prompt)
            return validate_server_url(ctx, param, value)
    return value


def check_folder_exists(ctx, param, value):
    if os.path.exists(value):
        fatal("Directory already exists: %s" % os.path.abspath(value))
    return value


@cli.command()
@click.argument("name", callback=check_folder_exists)
@click.option('--server-url', prompt=True, default="http://localhost", help="Server URL.", callback=validate_server_url)
@click.option('--publish-dir', prompt=True, default=os.path.join("data", "publish"), help="Publish directory.")
@click.option('--cadvisor', is_flag=True, prompt=True, help="Setup Cadvisor service.")
@click.option('--node-exporter', is_flag=True, prompt=True, help="Setup Node Exporter service.")
@click.option('--accounts', is_flag=True, default=False, prompt=True, help="Include web app for users registration.")
@click.option('--dev-server', is_flag=True, default=False, help="Setup application server for development.")
def create(name, server_url, publish_dir, cadvisor, node_exporter, accounts, dev_server):
    """Create a new deployment environment"""

    context = {
        "output_dir": name,
        "template_dir": os.path.join(BASE_DIR, "template"),
        "server_url": server_url,
        "accounts": accounts,
        "cadvisor": cadvisor,
        "node_exporter": node_exporter
    }

    if dev_server:
        context["server_src"] = click.prompt("Enter location of server's source code", type=click.Path(exists=True, resolve_path=True))

    click.secho("Creating a new deployment environment in directory: %s" % name, fg="cyan")
    os.mkdir(name)

    create_env_file(os.path.join(name, ".env"), {
        "SECRET_KEY": quote_string(generate_password(50)),
        "SERVER_URL": server_url
    })
    click.secho('Created ".env" file for the global settings', fg="yellow")

    create_env_file(os.path.join(name, "postgres.env"), {
        "POSTGRES_DB": "gisquick",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(10)
    })
    click.secho('Created "postgres.env" file for the main database settings', fg="yellow")

    if not os.path.isabs(publish_dir):
        publish_dir = os.path.join(name, publish_dir)
    if not os.path.exists(publish_dir):
        os.makedirs(publish_dir)
        try:
            os.chown(publish_dir, 1000, 1000)
        except Exception as e:
            click.secho('Failed to set owner of publish directory: %s' % e, fg="red")

        click.secho('Created directory for published projects', fg="yellow")


    template_dir = os.path.join(BASE_DIR, "template")
    conf_dirs = ["qgis", "migrations", "redis", "loki", "promtail", "prometheus"]
    for folder in conf_dirs:
        dest = os.path.join(name, folder)
        if not os.path.exists(dest):
            src = os.path.join(template_dir, folder)
            shutil.copytree(src, dest)


    compose_filename = os.path.join(context["template_dir"], "docker-compose.yml")
    with open(compose_filename) as file:
        config = yaml.load(file)

    # remove ending newline from last key of each service (if found)
    striped_newlines = {}
    for service_name, service in config["services"].items():
        striped_newlines[service_name] = remove_ending_newline(service)


    click.secho("Generating docker compose configuration...", fg="cyan")
    # click.secho("accounts extension: %s" % ("Yes" if accounts else "No"), fg="yellow")

    caddy_config(config, context)
    prometheus_config(config, context)

    app_server_config(config, context)
    if dev_server:
        server_dev_config(config, context)

    # remove disabled services
    services = config["services"]
    if not context["cadvisor"]:
        services.pop("cadvisor")
    if not context["node_exporter"]:
        services.pop("node-exporter")
    if not accounts:
        services.pop("web-accounts")

    volumes = config["volumes"]
    publish_volume_opts = volumes["publish"]["driver_opts"]
    if os.path.isabs(publish_dir):
        publish_volume_opts["device"] = publish_dir
    else:
        publish_volume_opts["device"] = os.path.join("{PWD}", publish_dir)

    # Adjust final config for pretty output

    # Sort keys in services
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


    compose_file = os.path.join(name, "docker-compose.yml")
    with open(compose_file, "w") as file:
        file.write("# Generated with: gisquick-cli\n\n")
        yaml.dump(config, file)

    click.secho("Docker Compose file saved", fg="cyan")


@cli.command()
@click.argument("compose_filename")
def use(compose_filename):
    """Set selected docker compose file as default"""
    if not os.path.exists(compose_filename):
        fatal("Compose file does not exists: %s" % compose_filename)
    create_symlink(compose_filename, "docker-compose.yml")


@cli.command()
@click.argument("args", nargs=-1)
@click.option("--source", help="Location of the migrations (driver://url)")
@click.option("--path", default="./migrations", help="Shorthand for --source=file://path", type=click.Path(exists=True))
def migrate(args, source, path):
    docker = ["docker", "run", "--rm"]
    migrate = []

    network = "%s_default" % os.path.basename(os.getcwd())
    docker.extend(["--network", network])

    if source:
        migrate.extend(["-source", source])
    else:
        docker.extend(["-v", "%s:/migrations" % os.path.abspath(path)])
        migrate.extend(["-path", "/migrations/"])

    docker.append("migrate/migrate")

    import subprocess
    from dotenv import dotenv_values
    config = dotenv_values("postgres.env")

    sslmode = config.get("POSTGRES_SSL_MODE", "prefer")
    db = "postgres://{user}:{password}@{host}/{dbname}?sslmode={sslmode}".format(
        user=config["POSTGRES_USER"],
        password=quote(config["POSTGRES_PASSWORD"]),
        host=config.get("POSTGRES_HOST", "postgres:5432"),
        dbname=config["POSTGRES_DB"],
        sslmode=sslmode
    )

    migrate.extend(["-database", db])
    migrate.extend(args)

    # docker run --rm -v `pwd`/migrations:/migrations --network gisquick_default migrate/migrate -path=/migrations/ -database "postgres://postgres:Xo7neeVo@postgres:5432/gisquick?sslmode=disable" up
    parts = [*docker, *migrate]
    # print(" ".join(parts))
    out = subprocess.run(parts)
    if out.returncode != 0:
        click.secho("Error: exit code: %d" % out.returncode, fg="red")


@cli.command()
def update_qgis_plugins():
    """Update QGIS plugins"""
    template_dir = os.path.join(BASE_DIR, "template")
    dest = "qgis"
    if os.path.exists(dest):
        shutil.rmtree(dest)
    src = os.path.join(template_dir, "qgis")
    shutil.copytree(src, dest)


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        # raise # For development
        fatal(str(e))
