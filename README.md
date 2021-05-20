# Log and metrics exporter for old Synology nas

## Presentation
 - Retreive logs and foarward them to graylog (GELF HTTP)
 - Retreive metrics (such as disk status, cpu, memory) and send them to influxdb
 - Tested with Synolocy CS407 and DSM 3.1

## Configuration
 - Copy `config.sample.yml` to `config.yml` and configure your connection settings for synogloy, graylog and influxdb
 - Build the container, mount the config file to `/app/config.yml` and run the container
 