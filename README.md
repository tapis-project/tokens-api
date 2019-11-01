# Tapis Tokens API

REST API for working with authentication tokens for the Tapis v3 Platform.


## Usage
This repository includes build files and other assets needed to start the service locally. Clone this
repository and follow the steps in the subsequent section.

### Start the API Locally
We are automating the management of the lifecycle workflow with `make`. You will need to install `make` it in order
to use the steps bellow.

The make system is generic and used by multiple Tapis services. Before following any of the sections below,
be sure to

```
$ export API_NAME=tokens
```

The `API_NAME` variable is used to let the `make` system know which Tapis service to work with.


#### First Time Setup
Currently the Tokens API is stateless, i.e., does not require any database. That may change in the future, but for now,
the only requirement is the service itself. Do the following steps to build and run the service locally:

1. `make build.api` - Build a new version of the API container image.
2. `docker-compose up -d tokens` - start a new version of the Tokens API.


### Quickstart
Use any HTTP client to interact with the running API. The following examples use `curl`.

#### Generate Tokens

Generate an access token:

```
$ curl -H "Content-type: application/json" -d '{"token_tenant_id": "dev", "token_type": "service", "token_username": "jstubbs"}'  localhost:5001/tokens
{
  "message": "Token generation successful.",
  "result": {
    "access_token": {
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoianN0dWJic0BkZXYiLCJ0YXBpcy90ZW5hbnRfaWQiOiJkZXYiLCJ0YXBpcy90b2tlbl90eXBlIjoiYWNjZXNzIiwidGFwaXMvZGVsZWdhdGlvbiI6ZmFsc2UsInRhcGlzL2RlbGVnYXRpb25fc3ViIjpudWxsLCJ0YXBpcy91c2VybmFtZSI6ImpzdHViYnMiLCJ0YXBpcy9hY2NvdW50X3R5cGUiOiJzZXJ2aWNlIiwiZXhwIjoxNTcxMDY4ODkyfQ.AZi6oIyJ5uml9hTjzPX58bYrb1j4zwuCDKC0_9SEBwJaT1IJVrzVow6lbXU-xudgzCwpOjOcj_Pg43vBrie0S6IijfN4iXaMAsuXKEfSCHPDXoNR3GPbvImeSiuqlMMofwCDJnVMc7Zq1kzRdeLBw4begtGCBEIx7RxtqbFYsg8",
      "expires_at": "2019-10-14 16:01:32.898216",
      "expires_in": 300
    }
  },
  "status": "success",
  "version": "dev"
}

```

The raw JWT is returned and by default includes only the standard Tapis claims.
One can base64 decode (or use a site like jwt.io) the payload string to 
see the claim set. For the token above, it is:

```
{
  "iss": "https://dev.api.tapis.io/tokens/v3",
  "sub": "jstubbs@dev",
  "tapis/tenant_id": "dev",
  "tapis/token_type": "access",
  "tapis/delegation": false,
  "tapis/delegation_sub": null,
  "tapis/username": "jstubbs",
  "tapis/account_type": "service",
  "exp": 1571068892
}
```


Generate access and refresh tokens:

```
$ curl -H "Content-type: application/json" -d '{"token_tenant_id": "dev", "token_type": "service", "token_username": "jstubbs", "generate_refresh_token": true}'  localhost:5001/tokens
{
  "message": "Token generation successful.",
  "result": {
    "access_token": {
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoianN0dWJic0BkZXYiLCJ0YXBpcy90ZW5hbnRfaWQiOiJkZXYiLCJ0YXBpcy90b2tlbl90eXBlIjoiYWNjZXNzIiwidGFwaXMvZGVsZWdhdGlvbiI6ZmFsc2UsInRhcGlzL2RlbGVnYXRpb25fc3ViIjpudWxsLCJ0YXBpcy91c2VybmFtZSI6ImpzdHViYnMiLCJ0YXBpcy9hY2NvdW50X3R5cGUiOiJzZXJ2aWNlIiwiZXhwIjoxNTcxMDY4OTQ5fQ.D1kGb17VpUNXwP78NeaTcmQ8LcgPQbPI6Ag0S7BNuu76t2QZBazi-WGLNqnsXFEc7zl1SoKSlsa1ROtqauDFH_AAqzKl-yWcfTZ-yElfeaAaqs-8XtgEmb3fEATiguty_g4fsh6k8yTq2cRfdysVqtyx-O0RZJP3K1E8W4RlMV8",
      "expires_at": "2019-10-14 16:02:29.428697",
      "expires_in": 300
    },
    "refresh_token": {
      "expires_at": "2019-10-14 16:07:29.429428",
      "expires_in": 600,
      "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoianN0dWJic0BkZXYiLCJ0YXBpcy90ZW5hbnRfaWQiOiJkZXYiLCJ0YXBpcy90b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTU3MTA2OTI0OSwidGFwaXMvYWNjZXNzX3Rva2VuIjp7ImlzcyI6Imh0dHBzOi8vZGV2LmFwaS50YXBpcy5pby90b2tlbnMvdjMiLCJzdWIiOiJqc3R1YmJzQGRldiIsInRhcGlzL3RlbmFudF9pZCI6ImRldiIsInRhcGlzL3Rva2VuX3R5cGUiOiJhY2Nlc3MiLCJ0YXBpcy9kZWxlZ2F0aW9uIjpmYWxzZSwidGFwaXMvZGVsZWdhdGlvbl9zdWIiOm51bGwsInRhcGlzL3VzZXJuYW1lIjoianN0dWJicyIsInRhcGlzL2FjY291bnRfdHlwZSI6InNlcnZpY2UiLCJ0dGwiOjMwMH19.JbRDyaV36gh4GEiOF9wGPxjQJZLVr2GVt-2CcRDziAQHFQ0SriJWu3bGFMEMht7QIOeFeSaYDPS_iDoVncEQAc4-UFi8JVDnoNKQ3BTgeoy2t_v99SXMRZZcfaf3YLTw_bCeUrgZm2lBogVqAV6QmpJ13VuILzbcyp3445eCy4c"
    }
  },
  "status": "success",
  "version": "dev"
}

```

Create a token with additional custom claims:
```
$ curl -H "Content-type: application/json" -d '{"token_tenant_id": "dev", "token_type": "service", "token_username": "jstubbs", "claims": {"client_id": "123", "scope": "dev"}}'  localhost:5001/tokens
{
  "message": "Token generation successful.",
  "result": {
    "access_token": {
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoianN0dWJic0BkZXYiLCJ0YXBpcy90ZW5hbnRfaWQiOiJkZXYiLCJ0YXBpcy90b2tlbl90eXBlIjoiYWNjZXNzIiwidGFwaXMvZGVsZWdhdGlvbiI6ZmFsc2UsInRhcGlzL2RlbGVnYXRpb25fc3ViIjpudWxsLCJ0YXBpcy91c2VybmFtZSI6ImpzdHViYnMiLCJ0YXBpcy9hY2NvdW50X3R5cGUiOiJzZXJ2aWNlIiwiZXhwIjoxNTcxMDY4OTc2LCJjbGllbnRfaWQiOiIxMjMiLCJzY29wZSI6ImRldiJ9.qt7tFo2sWhY0XpQx-l5IpACFUarpV81v9e5UzLmCX1EVYFiShfUd1drkNrqsOfMUlhxxwyV42umBrv019PSSSkTBsMAesHKjEqB6pn0huWkhZDKbTexcYT2M7Z20vZ9lh_a6HfBJXtA7VGcuqj8uKZVjw3Kql6tcb_N7Juw-7_0",
      "expires_at": "2019-10-14 16:02:56.422500",
      "expires_in": 300
    }
  },
  "status": "success",
  "version": "dev"
}
``` 

If we decode the token above, we see the additional claims:

```
{
  "iss": "https://dev.api.tapis.io/tokens/v3",
  "sub": "jstubbs@dev",
  "tapis/tenant_id": "dev",
  "tapis/token_type": "access",
  "tapis/delegation": false,
  "tapis/delegation_sub": null,
  "tapis/username": "jstubbs",
  "tapis/account_type": "service",
  "exp": 1571068976,
  "client_id": "123",
  "scope": "dev"
}
```

Use a refresh token to get a new access and refresh token pair:

```
$ curl -X PUT  -H "Content-type: application/json" -d '{"refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoiZGV2QGpzdHViYnMiLCJ0ZW5hbnRfaWQiOiJkZXYiLCJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTU2ODQ4NjIxMywiYWNjZXNzX3Rva2VuIjp7ImlzcyI6Imh0dHBzOi8vZGV2LmFwaS50YXBpcy5pby90b2tlbnMvdjMiLCJzdWIiOiJkZXZAanN0dWJicyIsInRlbmFudF9pZCI6ImRldiIsInRva2VuX3R5cGUiOiJhY2Nlc3MiLCJkZWxlZ2F0aW9uIjpmYWxzZSwidXNlcm5hbWUiOiJqc3R1YmJzIiwiYWNjb3VudF90eXBlIjoic2VydmljZSIsInR0bCI6MzAwfX0.d6L2s6uLidgsSpnoDsRB2qKJhpiK7moUX6Hd-wAZnms7BvT7uFfq5Pjx6EzChTXSyJYICtLVhOppkDjRKAQI3Rv6HyU3HMKC25r1_hRHLOmCzA2OK3G8Zm8cMAW8iAiamRCriocdxqnWignmDiuRmTGyhLeb2RGtYccX_yz3Hbw"}'  localhost:5001/tokens

{
  "message": "Token generation successful.",
  "result": {
    "access_token": {
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoianN0dWJic0BkZXYiLCJ0YXBpcy90ZW5hbnRfaWQiOiJkZXYiLCJ0YXBpcy90b2tlbl90eXBlIjoiYWNjZXNzIiwidGFwaXMvZGVsZWdhdGlvbiI6ZmFsc2UsInRhcGlzL2RlbGVnYXRpb25fc3ViIjpudWxsLCJ0YXBpcy91c2VybmFtZSI6ImpzdHViYnMiLCJ0YXBpcy9hY2NvdW50X3R5cGUiOiJzZXJ2aWNlIiwiZXhwIjoxNTcxMDY5NDQ1LCJjbGllbnRfaWQiOiIxMjMiLCJzY29wZSI6ImRldiJ9.b-OlkY9LgGVoIVBYhH_NLpP70WOJf2YeAxZhjxaCQT6KagYXg-4tglD5taP9aSO-pHSL6TTVa87trn4jNYqMM4RfYHlSIPdSG6wn6zkMDfCu-jPwMA1866BcxfvlALiDyDLYPLwiWdaZdoS7y1IHomJfyrGQWP74XQqS5eJ3Osc",
      "expires_at": "2019-10-14 16:10:45.776079",
      "expires_in": 300
    },
    "refresh_token": {
      "expires_at": "2019-10-14 16:15:45.777293",
      "expires_in": 600,
      "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoianN0dWJic0BkZXYiLCJ0YXBpcy90ZW5hbnRfaWQiOiJkZXYiLCJ0YXBpcy90b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTU3MTA2OTc0NSwidGFwaXMvYWNjZXNzX3Rva2VuIjp7ImlzcyI6Imh0dHBzOi8vZGV2LmFwaS50YXBpcy5pby90b2tlbnMvdjMiLCJzdWIiOiJqc3R1YmJzQGRldiIsInRhcGlzL3RlbmFudF9pZCI6ImRldiIsInRhcGlzL3Rva2VuX3R5cGUiOiJhY2Nlc3MiLCJ0YXBpcy9kZWxlZ2F0aW9uIjpmYWxzZSwidGFwaXMvZGVsZWdhdGlvbl9zdWIiOm51bGwsInRhcGlzL3VzZXJuYW1lIjoianN0dWJicyIsInRhcGlzL2FjY291bnRfdHlwZSI6InNlcnZpY2UiLCJjbGllbnRfaWQiOiIxMjMiLCJzY29wZSI6ImRldiIsInR0bCI6MzAwfX0.nX1SPfkxHgWI3Ycf3gBGi0C3PVcgGqq94rEuIERKKoJfrzzkd6EnLMxAxcqRZQDX9NYZWCNX3oR1IBQqpqZB0QTuSLFffQf35PuiH4VAeanOvRrMKyeKm1a9UCNEWPDrmd5MUC8GnTIlapbccDN7DeJ6iewHoeFU1GmJkq239lU"
    }
  },
  "status": "success",
  "version": "dev"
}
```

### Key Format and Generating a Public/Private Key Pair
(TODO - needs more detail)

The format of the public and private keys must be exact. Specifically, the `-----BEGIN RSA PRIVATE KEY-----\n`
and `-----END RSA PRIVATE KEY-----\n` must be included in the private key
and the `-----BEGIN RSA PUBLIC KEY-----\n` and `-----END RSA PUBLIC KEY-----\n` must
be included in the public key. 

For local development, generate a public/private RSA256 key pair with the following commands:

First, generate a private key and write it to a file -  
```
$ private_key=`openssl genrsa 1024`
$ echo $private_key > private.key
```

Extract the public key to a file:
```
echo "$private_key" | sed -e 's/^[ ]*//' | openssl rsa -pubout  > key.pub
```

Make sure to remove any spaces and covert line breaks to new line characters (`\n`)
in both the public and private key strings in the files. Them copy the strings
to the corresponding service config files, as necessary.
