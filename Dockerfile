FROM debian:bookworm-slim

EXPOSE 8897
## update apt, install python3, pip and venv
RUN apt-get update && apt-get install -y python3 python3-pip && apt install -y python3-venv
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
## set ENV so that python script knows it is in a container
ENV CONTAINERISED=YES
## Using the python 3 in the venv execute the script
CMD /env/bin/python3 riverlevel.py
