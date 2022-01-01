Following steps to restart the action server (manually create a new docker image and run it
as action server):
1) cd ~/chatbot-backend/
2) git pull
3) sudo docker login --username oogwaydocker --password '2ogway123!@'
4) sudo docker build . -t oogwaydocker/oogway-assistant:as_<mm>_<dd>_<yy>_<version>
5) sudo docker push oogwaydocker/oogway-assistant:as_<mm>_<dd>_<yy>_<version>
6) cd /etc/rasa/
7) sudo vim docker-compose.override.yml
   Replace the image tag with as_<mm>_<dd>_<yy>_<version>
8) sudo docker-compose pull
9) sudo docker-compose down && sudo docker-compose up -d
10) sudo docker logs rasa_app_1
   To check that the action server started successfully
