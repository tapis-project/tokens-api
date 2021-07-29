"""
Command line utility for managing public/private key pairs assigned to tenants for signing JWTs.
Use the service config, in accordance with the configschema.json, to configure aspects of the program.

Note that this service must run as the Tokens API, with the tokens service_name, and the dev_jwt_private_key must
be provided so that it can generate a JWT for the Tokens service and interact with the SK as such. Therefore, this
program uses the tokens-api base image


"""
import datetime
import json
import os
import sys
from common.config import conf
from common import errors

# whether to actually update the SK and/or Tenants API with changes.
# toggle this on or off for testing
ACTUALLY_RUN_UPDATES = os.environ.get('ACTUALLY_RUN_UPDATES', False)

# add packages to the path carefully -- each of the API packages (tokens, tenants) was originally called "service" so
# there can be some issues with imports if the path isn't correct
sys.path.insert(0, '/home/tapis')
sys.path.extend(['/home/tapis/service', '/home/tapis/keymgtService', '/home/tapis/tenantsService'])

# from tenantsService.service import db
# from tenantsService.service.models import Tenant, TenantHistory

# "service" here is the original tokens api service package:
from service.auth import t, generate_private_keypair_in_sk
valid_tenants = [tn.tenant_id for tn in t.tenant_cache.tenants]

DATA_DIR = os.environ.get('DATA_DIR', '/home/tapis/data')


def update_associate_site_pub_keys():
    """
    Updates the public keys defined in the Tenants API for an associate site. This function should
    only execute on the primary site, i.e., when conf.running_at_primary_site is true.
    """
    print("Top of update_associate_site_pub_keys")
    for tn in conf.tenants:
        pub_key_path = os.path.join(DATA_DIR, tn, 'pub.key')
        # read public key from the file and update it in the tenants db:
        with open(pub_key_path, 'r') as f:
            pub_key = f.read()
            update_tenant_pub_key(tn, pub_key)


def create_keys_for_tenant(tenant_id):
    """
    Calls the SK to generate a new public/private key pair for a given tenant id
    """
    print(f"Top of create_keys_for_tenant for tenant: {tenant_id}")
    try:
        priv_key, pub_key = generate_private_keypair_in_sk(tenant_id)
    except Exception as e:
        print(f"Got exception trying to generate keypair; e: {e}")
        raise e
    print(f"******** Generated new keys for tenant {tenant_id} *********")
    print("\n")
    print(f"Private Key:\n")
    print(priv_key)
    print("\n\nPublic Key:\n")
    print(pub_key)
    print("*************************************************************")
    return priv_key, pub_key


def update_tenant_pub_key(tenant_id, pub_key):
    """
    This function updates the public key to `pub_key` associated with tenant with id `tenant_id`.
    It makes the update directly in the Tenants model.
    """
    print(f"top of update_tenant_pub_key for tenant: {tenant_id}")
    try:
        t.tenants.update_tenant(tenant_id=tenant_id, public_key=pub_key)
    except Exception as e:
        print(f"got exception trying to update public key for tenant {tenant_id}; e: {e}")
        raise e
    print(f"public key updated for tenant {tenant_id}.")
    return None
    # tenant = Tenant.query.filter_by(tenant_id=tenant_id).first()
    # update_time = datetime.datetime.utcnow()
    # updated_by = 'tokens@admin'
    # prev_public_key = tenant.public_key
    # tenant.public_key = pub_key
    # tenant.last_update_time = update_time
    # tenant.last_updated_by = updated_by
    # changes_dict = {'public_key': { 'prev': prev_public_key,
    #                                 'new': pub_key }
    #                 }
    # tenant_history = TenantHistory(tenant_id=tenant.tenant_id,
    #                                update_time=update_time,
    #                                updated_by=updated_by,
    #                                updates_as_json=json.dumps(changes_dict)
    # )
    # db.session.add(tenant_history)
    # try:
    #     db.session.commit()
    # except Exception as e:
    #     print(f"got exception trying to commit db update for tenant {tenant_id}; e: {e}")
    #     raise e


def create_keys_for_primary_site():
    """
    Update the public/private keys at the primary site and then store the public keys with the tenants
    API. This function should only execute on the primary site, i.e., when conf.running_at_primary_site
    is true.
    """
    print("top of create_keys_for_primary_site")
    # first, create a public/private key pair for each tenant
    for tn in conf.tenants:
        priv_key, pub_key = create_keys_for_tenant(tn)
        # save the public key with the tenants API:
        update_tenant_pub_key(tn, pub_key)


def create_keys_for_associate_site():
    """
    Update the public/private keys at an associate site. This function runs at an associate site and does
    not update the associate public keys with the Tenants API.
    """
    print("top of create_keys_for_associate_site")
    for tn in conf.tenants:
        priv_key, pub_key = create_keys_for_tenant(tn)
        pub_key_path = os.path.join(DATA_DIR, tn, 'pub.key')
        # private key is saved with SK; public key gets written to a file:
        with open(pub_key_path, 'rw') as f:
            f.write(pub_key)


def validate_config():
    """
    Validates the config provided in the config.json file.
    """
    print(f"top of validate_config; found this config: {conf}")
    # we must be running as the Tokens API or this is not going to work.
    if not conf.service_name == 'tokens':
        raise errors.ServiceConfigError(f"Invalid config: conf.service_name must be 'tokens' not {conf.service_name}."
                                        f"This program must run as the Tokens API to be able to interact with SK.")
    # this keys management program leverages the Tokens API code for various calls
    if conf.use_sk:
        raise errors.ServiceConfigError(f"Invalid config: conf.use_sk must be False so that the tokens code running for "
                                        f"this program does not try to retrieve the private keys from the SK at"
                                        f"start up (they may not exist yet).")
    if not conf.dev_jwt_private_key:
        raise errors.ServiceConfigError(f"Invalid config: conf.dev_jwt_private_key required and must be the site admin "
                                        f"tenant private key.")
    # check that all tenant id's are valid
    for tn in conf.tenants:
        found = False
        for valid_tenant in t.tenant_cache.tenants:
            if valid_tenant.tenant_id == tn:
                found = True
                # check that all tenants in the list are owned by the site_id
                if not valid_tenant.site_id == conf.site_id:
                    raise errors.ServiceConfigError(f"Invalid tenant '{tn}' configured: tenant owned by {valid_tenant.site_id}, "
                                                    f"not owned by the configured site ({conf.site_id}.)")
        if not found:
            raise errors.ServiceConfigError(f"Invalid tenant {tn} configured: tenant not found; available "
                                            f"tenants: {valid_tenants}")

    if conf.running_at_primary_site:
        # first check for all required configs:

        # commenting these because we are now trying to go through tenants api ---
        # if not hasattr(conf, 'sql_db_url'):
        #     raise errors.ServiceConfigError("running_at_primary_site was 'true' so sql_db_url config required.")
        # if not hasattr(conf, 'postgres_user'):
        #     raise errors.ServiceConfigError("running_at_primary_site was 'true' so postgres_user config required.")
        # if not hasattr(conf, 'postgres_password'):
        #     raise errors.ServiceConfigError("running_at_primary_site was 'true' so postgres_password config required.")
        if not hasattr(conf, 'update_associate_site'):
            raise errors.ServiceConfigError("running_at_primary_site was 'true' so update_associate_site (t/f) config "
                                            "required.")
        if conf.update_associate_site:
            # when updating an associate site at the primary site, the associate site id is also required:
            if not hasattr(conf, 'associate_site_id'):
                raise errors.ServiceConfigError("running_at_primary_site was 'true' and 'update_associate_site' was "
                                                "true so associate_site_id config required.")
            # check that there is a directory for each tenant in the list of tenants
            for tn in conf.tenants:
                tn_dir_path = os.path.join(DATA_DIR, tn)
                if not os.path.isdir(tn_dir_path):
                    raise errors.ServiceConfigError(f"Did not find data directory for tenant {tn}"
                                                    f"Expected a directory at {tn_dir_path}.")
                # check for the existence of a public key file
                pub_key_path = os.path.join(DATA_DIR, tn, 'pub.key')
                if not os.path.isfile(pub_key_path):
                    raise errors.ServiceConfigError(f"Did not find public key for tenant {tn}"
                                                    f"Expected a public key file at {pub_key_path}.")

    # check that we can talk to the sk and that the tokens user has the tenant_definition_updater role
    try:
        has_role = t.sk.hasRole(roleName='tenant_definition_updater', user='tokens', tenant=conf.service_tenant_id)
    except Exception as e:
        raise errors.ServiceConfigError(f"Got an exception checking that tokens has the tenant_definition_updater role;"
                                        f"exception: {e}")
    if not has_role.isAuthorized:
        raise errors.ServiceConfigError(f"Got FALSE checking that tokens has the tenant_definition_updater role;"
                                        f"has_role: {has_role}")
    print("tokens user has necessary role.")


def main():
    validate_config()
    if not ACTUALLY_RUN_UPDATES:
        print('config was valid. ACTUALLY_RUN_UPDATES was False so exiting...')
        return
    print('config was valid and ACTUALLY_RUN_UPDATES was true, so starting the updates...')
    if conf.running_at_primary_site:
        if conf.update_associate_site:
            update_associate_site_pub_keys()
        else:
            create_keys_for_primary_site()
    else:
        create_keys_for_associate_site()


if __name__ == "__main__":
    main()