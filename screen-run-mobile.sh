function run_device {
  ADBNAME=$1
  CLIENT=$2

  screen /bin/bash -i -c "cd client ; adbset $ADBNAME && \\
    echo -ne '\\033k$CLIENT\\033\\\\' &&
    python speedtests.py \
      --platform android \
      --forever \
      --nap_after 15 \
      --nap_time 900 \
      --client $CLIENT ; \
    echo Done, hit enter to exit && read"
}

if [ $# == 0 ] ; then 
  # start the server
  screen /bin/bash -i -c 'cd server && screen -X title server && python server.py 8888; echo Done, hit enter to exit && read'

  # and then the clients
  run_device gndev android-galaxy-nexus-jb
  run_device s3 android-s3-ics
  run_device s3-mali android-s3-mali-ics
  run_device n7 android-neux-s7-jb

  echo Created all screens.
else
  run_device $*
fi


