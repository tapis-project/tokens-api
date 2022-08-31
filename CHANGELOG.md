# Change Log
All notable changes to this project will be documented in this file.


## 1.2.2 - 2022-09-02
This bug fix release fixes a small issue where Tokens API reported the JTI of the generated refresh token 
incorrectly within the JSON body of its response to POST requests generating refresh tokens.

### Breaking Changes:
- None.

### New features:
- None. 

### Bug fixes:
- Fix issue where the JTI returned in JWON response did not match that of the generated refresh token 
in a response to POST requests generating refresh tokens.


## 1.2.1 - 2022-08-24
This preview release adds support for token revocation.

### Breaking Changes:
- None.

### New features:
- A new endpoint has been added for token revocation. See issue #4 for more details. 

### Bug fixes:
- None.



## 1.2.0 - 2022-06-03
No updates made as part of this release.

### Breaking Changes:
- None.

### New features:
- None.

### Bug fixes:
- None.


## 1.1.1 - 2022-04-16
This release fixes a bug in the Tokens API that prevented services from being able to generate service
tokens using a service JWT authentication mechanism (see issue #3). It also reverts Tokens API back to
using the `tapis/flaskbase` image, as the `tapis/flaskbase-plugins` image has now become the
official flaskbase image. 

### Breaking Changes:
- None.

### New features:
- None.


## 1.1.0 - 2022-03-01
This release converts the Tokens API to using the new `tapipy-tapisservice` plugin-based 
Tapis Python SDK and makes updates necessary for supporting deployment automation provided
by the Tapis Deployer project.

### Breaking Changes:
- None.

### New features:
- Convert Tokens API to using the new `tapis/flaskbase-plugins` image.
- Support the initial version of the Tapis Deployer deployment automation. 

### Bug fixes:
- None.

## 1.0.0 - 2021-07-31
Initial production release of the Tapis Tokens API with support for generating signed
JWTs for both users and services. The Tokens API also provides an administrative endpoint
for updating the public/private key pair used for signing tokens associated with a tenant.
This repository also includes the build files and source  code for the `tapis/keys-mgt` image,
a command-line utility for initializing the public/private keys associate with a new site or set
of tenants.

For more details, please see the documentations: https://tapis.readthedocs.io/en/latest/technical/authentication.html

Live-docs: https://tapis-project.github.io/live-docs/

### Breaking Changes:
- Initial release.

### New features:
 - Initial release.

### Bug fixes:
- None.


## 0.1.0 - 2020-2-1 (target)
### Added
- Initial alpha release.

### Changed
- No change.

### Removed
- No change.
