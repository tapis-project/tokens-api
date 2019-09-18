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
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoiZGV2QGpzdHViYnMiLCJ0ZW5hbnRfaWQiOiJkZXYiLCJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZGVsZWdhdGlvbiI6ZmFsc2UsInVzZXJuYW1lIjoianN0dWJicyIsImFjY291bnRfdHlwZSI6InNlcnZpY2UiLCJleHAiOjE1Njg0MTcxODh9.JBTEK81Uvb1FNRFRm6oLt2Fog3OHmJa9Z4kkRAo7LQlYSbZZdHxXnzTtCXXTrYr7YFIHTQ8xcNLRjwT5nUOaLlmu8qzrjanRbC1XQHZa4jRUOK2ARBUZRK9yVaf2uvbBRJLW_Krzo90p3Pn-RWR2TwcYKtRAQlygKgXdkn1zmZw",
      "expires_at": "2019-09-13 23:26:28.196173",
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
  "sub": "dev@jstubbs",
  "tenant_id": "dev",
  "token_type": "access",
  "delegation": false,
  "username": "jstubbs",
  "account_type": "service",
  "exp": 1568417188
}
```


Generate access and refresh tokens:

```
$ curl -H "Content-type: application/json" -d '{"token_tenant_id": "dev", "token_type": "service", "token_username": "jstubbs", "generate_refresh_token": true}'  localhost:5001/tokens

{
  "message": "Token generation successful.",
  "result": {
    "access_token": {
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoiZGV2QGpzdHViYnMiLCJ0ZW5hbnRfaWQiOiJkZXYiLCJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZGVsZWdhdGlvbiI6ZmFsc2UsInVzZXJuYW1lIjoianN0dWJicyIsImFjY291bnRfdHlwZSI6InNlcnZpY2UiLCJleHAiOjE1Njg0MTcwNDR9.ZE_JqYRhpkAIyExgKP7YAIEIFNROJ4oft0G_dX1Q4WlPmCio2OQ4ajcxEjbfMUgPaFVBIgZ0IOQ76xaWIqtjVyoecCzJDX6U6RLEa-etnJzgfi3D6yjOCYahoAPiLwrCswgVqyGediEAxTvdWQUqK6xsrwiTB7iYT_HRDR_yb8Q",
      "expires_at": "2019-09-13 23:24:04.758644",
      "expires_in": 300
    },
    "refresh_token": {
      "expires_at": "2019-09-13 23:29:04.896390",
      "expires_in": 600,
      "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoiZGV2QGpzdHViYnMiLCJ0ZW5hbnRfaWQiOiJkZXYiLCJ0b2tlbl90eXBlIjoicmVmcmVzaCIsInVzZXJuYW1lIjoianN0dWJicyIsImFjY291bnRfdHlwZSI6InNlcnZpY2UiLCJleHAiOjE1Njg0MTczNDQsImFjY2Vzc190b2tlbiI6eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoiZGV2QGpzdHViYnMiLCJ0ZW5hbnRfaWQiOiJkZXYiLCJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZGVsZWdhdGlvbiI6ZmFsc2UsInVzZXJuYW1lIjoianN0dWJicyIsImFjY291bnRfdHlwZSI6InNlcnZpY2UifX0.rdCY7xGTIyMa04AtxIKeBCV06i0dI4kJC0R-uZQwRC6GIH2sNE9qc7YPE5qYTPpAWneuMd-pMc7SijW2DPkIQdGQOuVHd_m-L5aivVmyfh9IR69x2rx5RXFo5iLEDtz-9eBFw81JTXYpNc-W2mIYeTwQTijt_KbibwWa7Nvj2xw"
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
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoiZGV2QGpzdHViYnMiLCJ0ZW5hbnRfaWQiOiJkZXYiLCJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZGVsZWdhdGlvbiI6ZmFsc2UsInVzZXJuYW1lIjoianN0dWJicyIsImFjY291bnRfdHlwZSI6InNlcnZpY2UiLCJleHAiOjE1Njg4MzYwODMsImNsaWVudF9pZCI6IjEyMyIsInNjb3BlIjoiZGV2In0.WHi5ffPHJ8efiUMw0aOX4pgHYL4r_3gO1_QQ9McbWmqLOgjZIIHzu-qwJjLutJhXrIQEKkfJYWY-9pBenkehBEsxOwQh60_JQqV7NVohlcACPKcbFOm-rlWPQgdNzJCsJfxK4pG5S7mHjgrqdDrz-8OYD9mV34HP2ZNNZKUfmG4",
      "expires_at": "2019-09-18 19:48:03.738634",
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
  "sub": "dev@jstubbs",
  "tenant_id": "dev",
  "token_type": "access",
  "delegation": false,
  "username": "jstubbs",
  "account_type": "service",
  "exp": 1568836083,
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
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoiZGV2QGpzdHViYnMiLCJ0ZW5hbnRfaWQiOiJkZXYiLCJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZGVsZWdhdGlvbiI6ZmFsc2UsInVzZXJuYW1lIjoianN0dWJicyIsImFjY291bnRfdHlwZSI6InNlcnZpY2UiLCJleHAiOjE1Njg0ODYzMDN9.KBChtfKzuMqgQimFEkrSuc8XZHjStlsB8V6VnbKcIk_uIGTvXYI6rHY8KEC_b8DCaqP6Wm8eDslN4TP5O9XWkqTAG_ZMmk4VIFZNJFFyUcGth5eYdxuiFcDoRqd79zgVrrdp-ghvRrUl8EBOOV6HIkVsVhMTcgsI1TRO44RxiYk",
      "expires_at": "2019-09-14 18:38:23.513697",
      "expires_in": 300
    },
    "refres_token": {
      "expires_at": "2019-09-14 18:43:23.514270",
      "expires_in": 600,
      "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Rldi5hcGkudGFwaXMuaW8vdG9rZW5zL3YzIiwic3ViIjoiZGV2QGpzdHViYnMiLCJ0ZW5hbnRfaWQiOiJkZXYiLCJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTU2ODQ4NjYwMywiYWNjZXNzX3Rva2VuIjp7ImlzcyI6Imh0dHBzOi8vZGV2LmFwaS50YXBpcy5pby90b2tlbnMvdjMiLCJzdWIiOiJkZXZAanN0dWJicyIsInRlbmFudF9pZCI6ImRldiIsInRva2VuX3R5cGUiOiJhY2Nlc3MiLCJkZWxlZ2F0aW9uIjpmYWxzZSwidXNlcm5hbWUiOiJqc3R1YmJzIiwiYWNjb3VudF90eXBlIjoic2VydmljZSIsInR0bCI6MzAwfX0.TWcAX0N9UpNqvjAMsoAvURL-jIWJFLsnzkrzGdB3ypUumD-5XyiFyLdZeIqZeMfk9wtq8cVj0OS0upxY5jwJ_XTWz0BCRkMDPoya1zeaDW9FOsVwt91Y44aB8u9KzNf7hywd5tI3kikwUAGi0FsJXuvpkkwAzM1mk3I8plX8uQM"
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
