screen /bin/bash -i -c 'cd server && screen -X title server && python server.py 8888; echo Done, hit enter to exit && read'
cd client
screen /bin/bash -i -c 'adbset gndev && sh ./runner-mobile.sh android-galaxy-nexus-jb 8211; echo Done, hit enter to exit && read'
screen /bin/bash -i -c 'adbset s3 && sh ./runner-mobile.sh android-s3-ics 8212; echo Done, hit enter to exit && read'
screen /bin/bash -i -c 'adbset s3-mali && sh ./runner-mobile.sh android-s3-mali-ics 8213; echo Done, hit enter to exit && read'
screen /bin/bash -i -c 'adbset n7 && sh ./runner-mobile.sh android-nexus-7-jb 8214; echo Done, hit enter to exit && read'
echo Created all screens.

