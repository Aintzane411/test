#FROM python:3.7-alpine
#FROM python:3.8-alpine
FROM python:3.7

#RUN apk --no-cache add build-base linux-headers musl-dev
WORKDIR /app
ADD requirements.txt /app
RUN pip install --upgrade pip
RUN pip install --trusted-host pypi.python.org -r requirements.txt

ADD . /app
