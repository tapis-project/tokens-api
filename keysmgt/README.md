# Keys Management Program

## Introduction
The Keys Management program is a standalone command-line utility 
that can be run to create new private keys for a site's 
tenants. These private keys are used to sign the JWTs for the
tenant and must therefore be stored in the site's Security Kernel (SK) while the
corresponding public keys must be stored with the Tenants API (which always runs
at the primary site). 

This program runs in different modes depending on the type of site where it is run: 
when run at an associate site, it generates a new public/private key pair for each 
tenant owned by the site, it save the private key with the site's SK, and it writes the public key to
a file. The public key files can then be transferred to the primary site and saved
with the Tenants API using a separate run of this program.

When run at the primary site, this program can run in two different modes. It can be
run to update an associate site's public keys with the Tenants API, as mentioned above.
Set ``update_associate_site`` to ``true`` to run in this mode (see Configuration and Executions). 
Alternatively, this program can be used to update the keys for all tenants at the primary site. 
When run in this mode, this program performs all updates in one execution because it has
access to both the primary site's SK and the Tenants API.

## Configuration and Execution

The general format of the command used to run this program is as follows:

```
docker run -it \  
-v $(pwd)/my-config-file.json:/home/tapis/config.json \ 
-v $(pwd)/output:/home/tapis/data \ 
tapis/keys-mgt
```
for a dry run; or, when ready to actually make updates
```
docker run -it \  
-v $(pwd)/my-config-file.json:/home/tapis/config.json \ 
-v $(pwd)/output:/home/tapis/data \ 
-e ACTUALLY_RUN_UPDATES=true \
tapis/keys-mgt
```



### Configuration
This program uses a json configuration file conforming to the ``configschema.json`` file
in this directory. The program is packaged as a Docker image, ``tapis/keys-mgt``. It leverages the
Tokens API code and, in particular, uses the Tokens API schema and flaskbase common package for 
creating and managing the config object. As such, some configurations are required that
relate to the Tokens API rather than directly relating to this program.

Create a json configuration file and mount it when running the container, as shown in the
example above. In addition to basic jsonschema validation, the program tries to make sure the provided
json file is valid. 

Note that ``use_sk: false`` is required so that the Tokens API code that runs as part of this 
program doesn't try to retrieve the private keys from the SK.

The ``running_at_primary_site`` is required. When true, the ``update_associate_site`` should 
also be set: set it to ``true`` to update th public keys of an associate site.

The ``tenants`` configuration is a required json list of the tenant id's that this program should
generate and/or update keys for. Every tenant on the list must be owned by the site where this
program is run or else there will be errors.

Critically, this program must run with the Tokens API credentials so that
it can interact with both the SK and, in the case of running at the primary site, the Tenants
API to update tenants with the public keys. Note that it all actions takes by this program
are via API calls to SK and Tenants -- it does not need direct DB access to any service DBs. The
``dev_jwt_private_key`` config containing the current private key for the admin tenant where
this program will run must be provided.


### Input Key Files
When running at the primary site to update an associate site, this program assumes the
public keys are provided as files in a data directory mounted into the container. By default,
this directory is ``/home/tapis/data``, but it can be changed by setting the environment variable 
``DATA_DIR``. It assumes there is a directory in the data directory for each tenant with name
equal to the tenant id, and a public key file ``pub.key'`` within the tenant directory.
For example,
```
/home/tapis/data/uh-admin/pub.key
/home/tapis/data/uh-dev/pub.key
...
```

### Output Files
This program writes outputs to a directory in the container; by default it is ``/home/tapis/data``
but this can be changed by setting the environment variable ``DATA_DIR``. Regardless of the
container directory chosen, one should mount it to a volume on the host as shown above in 
``docker run`` command above.

In addition to writing file contents to stdout so that they are available via the
``docker logs`` command. We recommend **not** running with the ``--rm`` flag for this
reason.

### Dry Run
By default, this program runs without performing updates. To actually perform updates, set the environment 
variable ``ACTUALLY_RUN_UPDATES`` to a non-null string. 

## Real-World Use Cases

### Changing the default key on all tenants in the Primary site
When a new primary site instance of Tapis is intially started, the admin tenant and any
other tenants initially created (e.g., the dev tenant) are created with a temporary default
private key for signing tokens. These keys should be changed before any work is done in the tenants.

To change these keys, do the following:

1) make sure Tenants, SK and Tokens are all running with the default key.

2) Run the keys-mgt program with a json config file similar to the ``update-primary-site-initial-key.json`` as an
example. It is likely that the only configurations that will need to be updated from this file are the list
of tenant id's to update in the ``tenants`` config and the ``dev_jwt_private_key`` config.

3) Once the program has run, the Tenants, Tokens and SK pods will need to be restarted to get
service tokens signed with the new keys.
   
4) Once the SK has been restarted, it will now only honor the new public key. Tokens config must be 
updated, specifically the `dev_jwt_private_key`, with the new private key for the admin tenant so it can use this to sign its own token.


## Implementation
This program works by making API calls to the SK to generate new public/private key
pairs and to the Tenants API to update a tenant's definition with a new public key.
It does this by first getting a service token as the Tokens API and therefore must
be configured with the Token API's service credentials.