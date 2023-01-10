# $1 is path to root of flight_software repository

# driver
mkdir -p lib/configuration
find ./lib -type f -exec chmod 644 {} + # make files writable to update them
cp $1/state_machine/drivers/pycubedmini/lib/configuration/radio_configuration.py ./lib/configuration/
cp -r $1/state_machine/applications/flight/lib/radio_utils ./lib/
cp -r $1/state_machine/applications/flight/lib/logs.py ./lib/
find ./lib -type f -exec chmod 444 {} + # make files read-only to prevent changes
