# ANDROID_SERIAL=6410e088 sh ./runner-mobile.sh android-s3-ics 8111
# ANDROID_SERIAL=01467D5504010005 sh ./runner-mobile.sh android-galaxy-nexus-jb 8112
# ANDROID_SERIAL=015d2bc2825ff206 sh ./runner-mobile.sh android-nexus-7-jb 8113

CLIENT="$1"
PORT="$2"
shift 2
REBOOT_EVERY=15

if [ -z "$CLIENT" -o -z "$PORT" ] ; then
  echo "Must specify client and port"
  exit 1
fi

# set the window title
echo -n "\033k""$CLIENT""\033\\"

charge_delay=0
case "$ANDROID_SERIAL" in
	6410e088|42f0370803676f99|*)
		# Everything can't charge under load; so give it a 15 minute nap after a reboot to charge
		charge_delay=900
		;;
	*)
	;;
esac

count=0
while true ; do
    python speedtests.py --platform android --client $CLIENT --port $PORT \
	-t "webgl-perf-tests/webgl-performance-tests.html#viewport" \
	-t "aquarium/index.html" \
	$*
    count=$((count+1))
    if [ $count -ge $REBOOT_EVERY ] ; then
        count=0
	
        adb reboot
	print Sleeping for $charge_delay seconds to allow phone to charge...
	sleep $charge_delay
        adb wait-for-device
    fi

    echo =======================================
    sleep 30
done

