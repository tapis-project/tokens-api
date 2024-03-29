# image: tapis/tokens-api
FROM tapis/flaskbase:1.4.0

ADD requirements.txt /home/tapis/requirements.txt
RUN pip install -r /home/tapis/requirements.txt

WORKDIR /home/tapis

# ----API specific code
ENV TAPIS_API tokens
RUN touch /home/tapis/service.log

COPY configschema.json /home/tapis/configschema.json
COPY config-local.json /home/tapis/config.json
COPY service /home/tapis/service
COPY pytest.ini /home/tapis

RUN chown -R tapis:tapis /home/tapis
USER tapis

