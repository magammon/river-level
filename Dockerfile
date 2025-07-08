FROM alpine:latest

EXPOSE 8897
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /env/bin/python3 -c "import requests; requests.get('http://localhost:8898/health').raise_for_status()" || exit 1
## update apt, install python3, pip and venv
RUN apk update 
RUN apk add --no-cache python3 
RUN apk add --no-cache py3-pip
RUN apk add --no-cache py3-virtualenv
## update apt, upgrade all packages
RUN apk upgrade
RUN apk cache clean
## make directory for the venv
RUN mkdir /env
## make the venv in /env directory
RUN python3 -m venv /env
## copy the minimum requirements file for 
COPY requirements.txt /
## using the pip in the minimum requirements for the script
RUN /env/bin/pip install -r requirements.txt
## copy over the python script
COPY riverlevel.py /
## validate Python syntax before proceeding
RUN /env/bin/python3 -m py_compile riverlevel.py
## set ENV so that python script knows it is in a container
ENV CONTAINERISED=YES
## Using the python 3 in the venv execute the script
CMD /env/bin/python3 riverlevel.py
