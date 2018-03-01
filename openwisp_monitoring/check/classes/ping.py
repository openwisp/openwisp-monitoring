import subprocess


class Ping(object):
    def __init__(self, instance, params):
        self.instance = instance
        self.params = params

    def validate(self):
        # validate instance
        # validate params against schema
        pass

    def validate_instance(self):
        # check instance is of type device
        # check instance has last_ip
        pass

    def check(self):
        params = self.params
        count = params.get('count', 5)
        interval = params.get('interval', 25)
        bytes = params.get('bytes', 56)
        timeout = params.get('timeout', 500)
        ip = self.instance.config.last_ip
        command = [
            'fping',
            '-e',                # show elapsed (round-trip) time of packets
            '-c %s' % count,     # count of pings to send to each target,
            '-i %s' % interval,  # interval between sending pings(in ms)
            '-b %s' % bytes,     # amount of ping data to send
            '-t %s' % timeout,   # individual target initial timeout (in ms)
            '-q',
            ip
        ]
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        # fpings shows statistics on stderr
        output = stderr.decode('utf8')
        try:
            parts = output.split('=')
            min, avg, max = parts[-1].strip().split('/')
            sent, received, loss = parts[-2].strip() \
                                            .split(',')[0] \
                                            .split('/')
            loss = float(loss.strip('%'))
        except IndexError:
            # TODO: raise error output not recognized
            raise ValueError(stderr)
        return {
            'reachable': int(loss < 100),
            'loss': loss,
            'rtt_min': float(min),
            'rtt_avg': float(avg),
            'rtt_max': float(max),
        }
