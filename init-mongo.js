db = db.getSiblingDB('asterisk_realtime');
db.createCollection('extensions');
db.createCollection('queues');
db.createCollection('trunks');
print(">>> Banco asterisk_realtime inicializado com sucesso!");
