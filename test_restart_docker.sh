cd ~/chatbot-backend/
git pull
sudo docker login --username oogwaydocker --password '2ogway123!@'
sudo docker build . -t oogwaydocker/oogway-assistant:test_action_server
sudo docker push oogwaydocker/oogway-assistant:test_action_server
cd /etc/rasa/
sudo docker-compose pull
sudo docker-compose down && sudo docker-compose up -d
