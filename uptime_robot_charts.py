#!/usr/bin/env python3
import os
import requests
import datetime
import argparse

# See: https://uptimerobot.com/api/


#curl -X POST -H "Cache-Control: no-cache" -H "Content-Type: application/x-www-form-urlencoded" -d 'api_key=enterYourAPIKeyHere&format=json' "https://api.uptimerobot.com/v2/getAccountDetails"


class UptimeRobotClient():

    def __init__(self, api_key):
        self.api_key = api_key

    def post(self, url, data={}):
        url = 'https://api.uptimerobot.com/v2/' + url
        data.update({
            'api_key': self.api_key,
        })

        response = requests.post(
            url = url,
            data = data,
            headers = {
                'Cache-Control': 'no-cache',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
        )

        return response

    def get_monitor_ids(self, monitor_friendly_names):

        def lookup(data, name):
            for monitor in data['monitors']:
                if monitor['friendly_name'] == name:
                    return monitor['id']
            raise Exception('Monitor "%s" not found' % name)
            return 0

        result = {}
        data = self.post('getMonitors').json()
        for name in monitor_friendly_names:
            id = lookup(data, name)
            if id:
                result[name] = id
        return result

    def get_retrieve_response_times(self, monitor_id, start_date, end_date):

        # Convert to unix timestamp
        start_date = int(datetime.datetime.timestamp(start_date-datetime.timedelta(hours=8)))
        end_date = int(datetime.datetime.timestamp(end_date-datetime.timedelta(hours=24)))

        response = self.post(
            url='getMonitors',
            data = {
                'monitors': monitor_id,
                'custom_uptime_ranges': '%d_%d' % (start_date, end_date),
                'response_times': 1,
                'response_times_average': 60 * 24,
                'response_times_start_date': start_date,
                'response_times_end_date': end_date,
                # 'logs': 1,
                # 'logs_start_date': start_date,
                # 'logs_end_date': end_date,
            }
        )

        return response.json()['monitors'][0]


def main():

    # read api key
    try:
        api_key = os.environ['UPTIME_ROBOT_APY_KEY']
    except KeyError:
        print('ERROR: api key is required; please create env variable UPTIME_ROBOT_APY_KEY')
        return 1

    # Create client
    client = UptimeRobotClient(api_key)

    names = [
        'aaa',
        'bbb',
    ]

    result = client.get_monitor_ids(names)
    print(result)

    start_date = datetime.datetime(2023, 1, 1, 0, 0, 0).replace(tzinfo=datetime.timezone.utc)
    end_date = datetime.datetime(2023, 4, 1, 0, 0, 0).replace(tzinfo=datetime.timezone.utc)

    for name, id in result.items():
        result = client.get_retrieve_response_times(
            id,
            start_date,
            end_date
        )

        print('site          :' + result['friendly_name'])
        print('response time :' + result['average_response_time'])
        print('uptime %      :' + result['custom_uptime_ranges'])

        print('response times:')
        for t in result['response_times']:
            print('%s --> %5d' % (datetime.datetime.fromtimestamp(t['datetime']), t['value']))


if __name__ == '__main__':
    main()
