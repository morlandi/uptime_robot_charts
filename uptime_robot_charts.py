#!/usr/bin/env python3
import os
import requests
import datetime
import calendar
import argparse

# See: https://uptimerobot.com/api/
#
# Example:
# curl -X POST -H "Cache-Control: no-cache" -H "Content-Type: application/x-www-form-urlencoded" -d 'api_key=enterYourAPIKeyHere&format=json' "https://api.uptimerobot.com/v2/getAccountDetails"


class UptimeRobotClient():

    def __init__(self, api_key):
        self.api_key = api_key

    def post(self, url, data={}):
        """
        Helper to post a generic request
        """
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

    def list_monitors(self):
        data = self.post('getMonitors').json()

        # TODO: use pagination if required
        assert data['pagination']['total'] <= data['pagination']['limit'], "Use pagination !"

        names = [row['friendly_name'] for row in data['monitors']]
        return names

    def lookup_monitor_ids(self, monitor_friendly_names):

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

    def date_to_timestamp(self, d, offset_hours=0):
        # Helper to convert a datetime.date to a unix timestamp
        dt = datetime.datetime(d.year, d.month, d.day).replace(tzinfo=datetime.timezone.utc)
        if offset_hours:
            dt = dt - datetime.timedelta(hours=offset_hours)
        t = dt.timestamp()
        return int(t)

    def retrieve_response_times(self, monitor_id, start_date, end_date):

        # Unfortunately we need to collect one week at a time or less
        data = []
        first = start_date
        while first < end_date:
            last = min(first + datetime.timedelta(days=6), end_date)

            response = self.post(
                url='getMonitors',
                data = {
                    'monitors': monitor_id,
                    #'custom_uptime_ranges': '%d_%d' % (start_date, end_date),
                    'response_times': 1,
                    'response_times_average': 60 * 24,
                    'response_times_start_date': self.date_to_timestamp(first, 8),
                    'response_times_end_date': self.date_to_timestamp(last, 8),
                    # 'logs': 1,
                    # 'logs_start_date': start_date,
                    # 'logs_end_date': end_date,
                }
            )
            data += response.json()['monitors'][0]['response_times']
            first = last

        # Remove duplicates
        data2 = []
        for row in data:
            if not row['datetime'] in [d['datetime'] for d in data2]:
                data2.append(row)

        # We asked to time averages over 24 hours, but sometimes receive mixed results
        sorted_data = sorted(data2, key=lambda d: d['datetime'])
        return [
            {'datetime': datetime.datetime.fromtimestamp(t['datetime']), 'value': t['value'], }
            for t in sorted_data
        ]

    def retrieve_uptime(self, monitor_id, start_date, end_date):

        response = self.post(
            url='getMonitors',
            data = {
                'monitors': monitor_id,
                'custom_uptime_ranges': '%d_%d' % (
                    self.date_to_timestamp(start_date),
                    self.date_to_timestamp(end_date),
                ),
            }
        )

        data = response.json()['monitors'][0]
        return float(data['custom_uptime_ranges'])


def guess_quarter():
    """
    By default, we select the last full quarter preceeding today
    """

    today = datetime.date.today()

    q0 = today.month // 3  # 0 to 3
    y = today.year
    if q0 == 0:
        # return last quarter of previous year
        quarter = 4
        year = y - 1
    else:
        # return previous quarter
        quarter = (q0 - 1) + 1
        year = y

    return quarter, year


def build_date_range(quarter, year):
    first_month = 1 + ((quarter - 1) * 3)
    last_month = quarter * 3
    start_date = datetime.date(year, first_month, 1)
    end_date = datetime.date(year, last_month, calendar.monthrange(year, last_month)[1])
    return start_date, end_date


def main():

    # read api key
    try:
        api_key = os.environ['UPTIME_ROBOT_APY_KEY']
    except KeyError:
        print('ERROR: api key is required; please create env variable UPTIME_ROBOT_APY_KEY')
        return 1

    # Create client
    client = UptimeRobotClient(api_key)
    quarter, year = guess_quarter()

    # Parse command line
    parser = argparse.ArgumentParser(description='Produce data backups, and optionally remove obsolete files')
    parser.add_argument('-m', '--monitors', nargs='*', help='One or more friendly names for Monitors to be analyzed')
    parser.add_argument('-q', '--quarter', type=int, choices=range(1, 5), help="quarter (1 to 4); default=%d" % quarter)
    parser.add_argument('-y', '--year', type=int, help="default=%d" % year)
    parser.add_argument('-d', '--details', action='store_true', default=False, help="print details")

    args = parser.parse_args()
    monitor_names = args.monitors

    if args.quarter is not None:
        quarter = args.quarter
    if args.year is not None:
        year = args.year


    if not monitor_names:
        names = client.list_monitors()
        print('Available monitors:')
        print(names)

    else:

        start_date, end_date = build_date_range(quarter, year)
        monitors = client.lookup_monitor_ids(monitor_names)
        for name, id in monitors.items():

            uptime = client.retrieve_uptime(
                id,
                start_date,
                end_date
            )

            response_times = client.retrieve_response_times(
                id,
                start_date,
                end_date
            )

            values = [row['value'] for row in response_times]
            average_response_time = sum(values) / len(values)

            print('----------------------------------------')
            print('"%s" q = %d, y = %d' % (name, quarter, year))
            print('----------------------------------------')
            print('uptime: %.3f %%' % uptime)
            print('average_response_time: %.2f [ms]' % average_response_time)

            if args.details:
                print('response times:')
                for t in response_times:
                    print('%s --> %5d' % (t['datetime'], t['value']))
                print('total: %d' % len(response_times))


if __name__ == '__main__':
    main()
