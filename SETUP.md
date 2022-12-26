# Setup

_(This requires changing.)_

## Install the dependencies

There are two paths to installing the dependencies for development.

### Using `docker-compose`

You can use Docker Compose to run the bot while
developing, as all necessary dependencies are handled for you. After
installation and ensuring the `docker-compose` command works, you need to:

1. Create a data directory and config file by following the
   [docker setup instructions](docker#setup).

2. Create a docker volume pointing to that directory:

   ```
   docker volume create \
     --opt type=none \
     --opt o=bind \
     --opt device="/path/to/data/dir" data_volume
   ```

Run `docker/start-dev.sh` to start the bot.

**Note:** If you are trying to connect to a Synapse instance running on the
host, you need to allow the IP address of the docker container to connect. This
is controlled by `bind_addresses` in the `listeners` section of Synapse's
config. If present, either add the docker internal IP address to the list, or
remove the option altogether to allow all addresses.

### Running natively

If you would rather not or are unable to run docker, the following will
instruct you on how to install the dependencies natively:

#### Install libolm (optional)

You can install [libolm](https://gitlab.matrix.org/matrix-org/olm) from source,
or alternatively, check your system's package manager. Version `3.0.0` or
greater is required.

**(Optional) postgres development headers**

By default, the bot uses SQLite as its storage backend. This is fine for a few
hundred users, but if you plan to support a much higher volume of requests, you
may consider using Postgres as a database backend instead.

If you want to use postgres as a database backend, you'll need to install
postgres development headers:

Debian/Ubuntu:

```
sudo apt install libpq-dev libpq5
```

Arch:

```
sudo pacman -S postgresql-libs
```

#### Install Python dependencies

Create and activate a Python 3 virtual environment:

```
virtualenv -p python3 env
source env/bin/activate
```

Install python dependencies:

```
pip install -e .
# Using requirements.txt
pip install -r requirements.txt
```

This project uses [Wand](https://docs.wand-py.org) and the `pango-view` CLI command, requiring you to install ImageMagick library and Pango CLI tools.

Debian/Ubuntu:

```
sudo apt install libmagickwand-dev pango1.0-tools
```

Arch:

```
sudo pacman -S imagemagick pango
```

(Optional) If you want to use postgres as a database backend, use the following
command to install postgres dependencies alongside those that are necessary:

```
pip install -e ".[postgres]"
```

## Install fonts

[Sarasa Gothic](https://github.com/be5invis/Sarasa-Gothic) should be installed for best quote image results. It is also recommanded to install the Noto Color Emoji font on the machine running the bot.

## Build word segmenter

Use Rust to build the segmenter:

```
cd cutword
cargo build --release
```

Copy the `target/release/nyx_bot-cutword` to a `PATH` avaliable to the bot.

You can also use the Python one located in `cutword/nyx_bot-cutword.py`.

## Configuration

Copy the sample configuration file to a new `config.yaml` file.

```
cp sample.config.yaml config.yaml
```

Edit the config file. The `matrix` section must be modified at least.

#### (Optional) Set up a Postgres database

Create a postgres user and database for matrix-reminder-bot:

```
sudo -u postgresql psql createuser nio-template -W  # prompts for a password
sudo -u postgresql psql createdb -O nio-template nio-template
```

Edit the `storage.database` config option, replacing the `sqlite://...` string with `postgres://...`. The syntax is:

```
database: "postgres://username:password@localhost/dbname?sslmode=disable"
```

See also the comments in `sample.config.yaml`.

## Running

### Docker

Refer to the docker [run instructions](docker/README.md#running).

### Native installation

Make sure to source your python environment if you haven't already:

```
source env/bin/activate
```

Then simply run the bot with:

```
nyx-bot
```

You'll notice that "nyx-bot" is scattered throughout the codebase. When
it comes time to modifying the code for your own purposes, you are expected to
replace every instance of "nyx-bot" and its variances with your own
project's name.

By default, the bot will run with the config file at `./config.yaml`. However, an
alternative relative or absolute filepath can be specified after the command:

```
nyx-bot other-config.yaml
```

## Final steps

Invite the bot to a room and it should accept the invite and join.
