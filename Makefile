# Recipes for building images, and applying data migrations and running services locallu.
# NOTE - tab characters are required within recipes; Do NOT edit this file in an editor that supplies spaces; for example,
#        lots of Python IDEs like PyCharm won't work because they are (rightly) configured to insert spaces, even if you
#        type a TAB character. If you see an error like " *** missing separator.  Stop." you're missing some tabs!
#
#        CONSIDER USING VIM (sigh!) WHICH ACTUALLY HAS GOOD MAKEFILE EDITING SUPPORT.


# it is required that the operator export API_NAME=<name_of_the_api> before using this makefile/
api=${API_NAME}

cwd=$(shell pwd)


# ----- build images

build.api:
	cd $(cwd); touch service.log; docker build -t tapis/$(api)-api .;

build: build.api


# ----- wipe the local environment by removing all containers
clean:
	docker-compose down

# ----- start databases
run_dbs: build.api clean
	cd $(cwd); docker-compose up -d postgres

# ----- connect to db as root
connect_db:
	docker-compose exec postgres psql -Upostgres

# ----- initialize databases; run this target once per database installation
init_dbs: run_dbs
	echo "wait for db to start up..."
	sleep 4
	docker cp new_db.sql ${api}-api_postgres_1:/db.sql
	docker-compose exec postgres psql -Upostgres -f /db.sql

# ----- wipe database and associated data
wipe: clean
	docker volume rm $(api)-api_pgdata
	rm -rf migrations

# ----- run migrations
migrate.upgrade: build.migrations
	docker-compose run --rm migrations upgrade
	
