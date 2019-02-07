#!/usr/bin/env python

import pylxd
import os
import sys
import json
import multiprocessing
import subprocess
import commands 
import collections
import re

# pylxd dont have storage functions yet
# so define storage pool name here
lxdstorage = "default"
outputtype = "influx"

SYMBOLS = {
    'customary'     : ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'),
    'customary_ext' : ('byte', 'kilo', 'mega', 'giga', 'tera', 'peta', 'exa',
                       'zetta', 'iotta'),
    'iec'           : ('Bi', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi'),
    'iec_ext'       : ('byte', 'kibi', 'mebi', 'gibi', 'tebi', 'pebi', 'exbi',
                       'zebi', 'yobi'),
}

# conversion of human readable to bytes
def human2bytes(s):
  init = s
  num = ""
  while s and s[0:1].isdigit() or s[0:1] == '.':
    num += s[0]
    s = s[1:]
  num = float(num)
  letter = s.strip()
  for name, sset in SYMBOLS.items():
    if letter in sset:
      break
  else:
    if letter == 'k':
      # treat 'k' as an alias for 'K' as per: http://goo.gl/kTQMs
      sset = SYMBOLS['customary']
      letter = letter.upper()
    else:
      raise ValueError("can't interpret %r" % init)
  prefix = {sset[0]:1}
  for i, s in enumerate(sset[1:]):
    prefix[s] = 1 << (i+1)*10
  return int(num * prefix[letter])

# search for device name by the major:minor number
#def ask_sysfs(majorminor):
#  from glob import glob
#  needle = "%s" % (majorminor)
#  files = glob("/sys/class/block/*/dev")
#  for f in files:
#    if file(f).read().strip() == needle:
#      return os.path.dirname(f).split('/')[-1]
#  return None

# init empty values
client = pylxd.Client()
lxdmetrics = {}
globalmetrics = {}
globalmetrics['cpu'] = {}
globalmetrics['mem'] = {}
globalmetrics['hdd'] = {}
globalmetrics['other'] = {}
globalmetrics['cpu']['given'] = 0
globalmetrics['mem']['given'] = 0
globalmetrics['hdd']['given'] = 0
globalmetrics['mem']['used'] = 0
globalmetrics['hdd']['used'] = 0
globalmetrics['containers'] = {}
globalmetrics['containers']['total'] = 0
globalmetrics['containers']['running'] = 0
globalmetrics['other']['live'] = 1

# some global metrics for bare metal
globalmetrics['cpu']['total'] = multiprocessing.cpu_count()
globalmetrics['mem']['total'] = mem_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')  # e.g. 4015976448
try:
  globalmetrics['hdd']['total'] = human2bytes(commands.getoutput("zpool list " + lxdstorage + " | grep " + lxdstorage + " | awk -F ' +' '{print $2}'")+'B')
except:
  # storage not found, or we dont have zfs storage
  globalmetrics['hdd']['total'] = 1
  pass

# fetch all containers
for container in client.containers.all():
  cno = container.state()	# cno = cno
  
  # counters
  try:
    globalmetrics['containers']['total'] += 1
  except KeyError:
    globalmetrics['containers']['total'] = 1
    pass

  try:
    globalmetrics['containers'][cno.status.lower()] += 1
  except KeyError:
    globalmetrics['containers'][cno.status.lower()] = 1
    pass

  # list init
  cn = container.name.lower()	# cn = containername
  lxdmetrics[cn] = {}
  
  # set container status to 1 if running, otherwise 0 - so in grafana you should display this (or use it as alert)
  if cno.status.lower() == "running":
    lxdmetrics[cn]['running'] = 1
  else:
    lxdmetrics[cn]['running'] = 0
    # if container is not running continue to next element in for loop
    continue

  # metrics
  lxdmetrics[cn]['mem'] = {}
  lxdmetrics[cn]['swap'] = {}
  lxdmetrics[cn]['cpu'] = {}
  lxdmetrics[cn]['disk'] = {}
  lxdmetrics[cn]['blkio'] = {}
  lxdmetrics[cn]['processes'] = cno.processes
  lxdmetrics[cn]['mem']['usage'] = cno.memory['usage']
  lxdmetrics[cn]['mem']['peak'] = cno.memory['usage_peak']
  lxdmetrics[cn]['swap']['usage'] = cno.memory['swap_usage']
  lxdmetrics[cn]['swap']['peak'] = cno.memory['swap_usage_peak']
  lxdmetrics[cn]['cpu']['usage'] = cno.cpu['usage']
  globalmetrics['mem']['used'] += lxdmetrics[cn]['mem']['usage']

  # exec metrics (metric fetched via lxc exec direct from inside container)
  # Not Working right now - maybe rework to try/except, just commenting it out for now
  # /tmp size and usage
  #ccommand = "df /tmp"
  #ce = container.execute(ccommand.split())
  # class values: exit_code stdout stderr
  #if ce.exit_code == 0:
  #  for line in ce.stdout.split('\n'):
  #    if re.match("(.*)/tmp$", line):
  #      lxdmetrics[cn]['disk']['tmp'] = {}
  #      lxdmetrics[cn]['disk']['tmp']['usage'] = int(line.split()[2])*1024
  #      lxdmetrics[cn]['disk']['tmp']['limit'] = int(line.split()[3])*1024
  #      lxdmetrics[cn]['disk']['tmp']['usage_pct'] = int(lxdmetrics[cn]['disk']['tmp']['usage'] * 100 / lxdmetrics[cn]['disk']['tmp']['limit'])

  # try/except metrics
  try:
    lxdmetrics[cn]['mem']['limit'] = human2bytes(container.expanded_config['limits.memory'])
  except:
    # if there is no limit - container should use all available resources
    lxdmetrics[cn]['mem']['limit'] = globalmetrics['mem']['total']
    pass
  lxdmetrics[cn]['mem']['usage_pct'] = int(lxdmetrics[cn]['mem']['usage'] * 100 / lxdmetrics[cn]['mem']['limit'])
  globalmetrics['mem']['given'] += lxdmetrics[cn]['mem']['limit']

  # TODO - polishing for multiple storage pools
  try:
    for disk in cno.disk:
      lxdmetrics[cn]['disk'][disk] = {}
      lxdmetrics[cn]['disk'][disk]['usage'] =  cno.disk[disk]['usage']
      try:
        lxdmetrics[cn]['disk'][disk]['limit'] =  human2bytes(container.expanded_devices[disk]['size'])
      except:
        # if there is no disk limit - container shoud use all available disk space
        lxdmetrics[cn]['disk'][disk]['limit'] = globalmetrics['hdd']['total']
        pass
      lxdmetrics[cn]['disk'][disk]['usage_pct'] = int(lxdmetrics[cn]['disk'][disk]['usage'] * 100 / lxdmetrics[cn]['disk'][disk]['limit'])
      globalmetrics['hdd']['given'] += lxdmetrics[cn]['disk'][disk]['limit']
  except:
    pass

  try:
    globalmetrics['hdd']['used'] += lxdmetrics[cn]['disk'][disk]['usage']
  except:
    # container doesnt have own disk device - we cannot determine used space
    globalmetrics['hdd']['used'] += 1

  try:
    lxdmetrics[cn]['cpu']['limit'] = int(container.expanded_config['limits.cpu'])
  except:
    # if there is no cpu limit - container should use all available resources
    lxdmetrics[cn]['cpu']['limit'] = globalmetrics['cpu']['total']
    pass
  lxdmetrics[cn]['cpu']['usage_percpu'] = int(round(lxdmetrics[cn]['cpu']['usage'] / lxdmetrics[cn]['cpu']['limit']))
  globalmetrics['cpu']['given'] += lxdmetrics[cn]['cpu']['limit']
  
  try:
    lxdmetrics[cn]['net'] = {}
    for interface in cno.network:
      lxdmetrics[cn]['net'][interface] = {}
      lxdmetrics[cn]['net'][interface]['pkts_out'] = cno.network[interface]['counters']['packets_sent']
      lxdmetrics[cn]['net'][interface]['pkts_in'] = cno.network[interface]['counters']['packets_received']
      lxdmetrics[cn]['net'][interface]['bytes_out'] = cno.network[interface]['counters']['bytes_sent']
      lxdmetrics[cn]['net'][interface]['bytes_in'] = cno.network[interface]['counters']['bytes_received']
  except:
    pass

  # cgroup metrics - read them only when container is running
  if lxdmetrics[cn]['running'] == 1:
    if os.path.exists('/sys/fs/cgroup/cpu,cpuacct/lxc.monitor/%s/cpu.shares' % cn):
      try:
        with open('/sys/fs/cgroup/cpu,cpuacct/lxc.monitor/%s/cpu.shares' % cn, 'rt') as cgfile:
          lxdmetrics[cn]['cpuprio'] = int(cgfile.read())
      except:
        pass
  
    if os.path.exists('/sys/fs/cgroup/blkio/lxc.payload/%s/blkio.weight' % cn):
      try:
        with open('/sys/fs/cgroup/blkio/lxc.payload/%s/blkio.weight' % cn, 'rt') as cgfile:
          lxdmetrics[cn]['hddprio'] = int(cgfile.read())
      except:
        pass

    if os.path.exists('/sys/fs/cgroup/blkio/lxc.payload/%s/blkio.throttle.io_serviced' % cn):
      try:
        with open('/sys/fs/cgroup/blkio/lxc.payload/%s/blkio.throttle.io_serviced' % cn, 'rt') as cgfile:
          for line in cgfile.readlines():
            # sum every read or write occuring
            if "Read" in line:
              #device = ask_sysfs(line.split()[0])
              try: 
                lxdmetrics[cn]['blkio']['iops_read'] += int(line.split()[2])
              except KeyError:
                lxdmetrics[cn]['blkio']['iops_read'] = int(line.split()[2])
                pass
            if "Write" in line:
              #device = ask_sysfs(line.split()[0])
              try: 
                lxdmetrics[cn]['blkio']['iops_write'] += int(line.split()[2])
              except KeyError:
                lxdmetrics[cn]['blkio']['iops_write'] = int(line.split()[2])
                pass
            if "Total" in line.split()[0]:
              #device = ask_sysfs(line.split()[0])
              try:
                lxdmetrics[cn]['blkio']['iops_total'] += int(line.split()[1])
              except KeyError:
                lxdmetrics[cn]['blkio']['iops_total'] = int(line.split()[1])
                pass
      except:
        pass
  
    if os.path.exists('/sys/fs/cgroup/blkio/lxc/%s/blkio.throttle.io_service_bytes' % cn):
      try:
        with open('/sys/fs/cgroup/blkio/lxc/%s/blkio.throttle.io_service_bytes' % cn, 'rt') as cgfile:
          for line in cgfile.readlines():
            if "Read" in line:
              #device = ask_sysfs(line.split()[0])
              try:
                lxdmetrics[cn]['blkio']['bytes_read'] += int(line.split()[2])
              except KeyError: 
                lxdmetrics[cn]['blkio']['bytes_read'] = int(line.split()[2])
                pass
            if "Write" in line:
              #device = ask_sysfs(line.split()[0])
              try:
                lxdmetrics[cn]['blkio']['bytes_write'] += int(line.split()[2])
              except KeyError:
                lxdmetrics[cn]['blkio']['bytes_write'] = int(line.split()[2])
                pass
            if "Total" in line.split()[0]:
              #device = ask_sysfs(line.split()[0])
              try:
                lxdmetrics[cn]['blkio']['bytes_total'] += int(line.split()[1])
              except KeyError:
                lxdmetrics[cn]['blkio']['bytes_total'] = int(line.split()[1])
                pass
      except:
        pass

  # cgroup end
  # metrics end

# some global metrics count:
globalmetrics['mem']['used_pct'] = int(globalmetrics['mem']['used'] * 100 / globalmetrics['mem']['total'])
globalmetrics['mem']['given_pct'] = int(globalmetrics['mem']['given'] * 100 / globalmetrics['mem']['total'])
globalmetrics['hdd']['used_pct'] = int(globalmetrics['hdd']['used'] * 100 / globalmetrics['hdd']['total'])
globalmetrics['hdd']['given_pct'] = int(globalmetrics['hdd']['given'] * 100 / globalmetrics['hdd']['total'])
globalmetrics['containers']['notrunning'] = globalmetrics['containers']['total'] - globalmetrics['containers']['running']

if outputtype == "json":
  print json.dumps(lxdmetrics)
  print json.dumps(globalmetrics)
  sys.exit()

# influx output
output = []
# loop for containers metrics
for container, metric in lxdmetrics.iteritems():
    header = "lxd,type=container,hostname=" + container
    try:
      # try to split hostname to name and instance by dash delimiter
      header += ",name=" + container.split('-')[0] + ",instance=" + container.split('-')[1]
    except:
      #IndexError (probably)
      # if error, keep it as is so this script shoudl work in default environment out of the zerops
      pass
    if metric['running'] == 1:
      output.append(header + ",metric=status running=" + str(metric['running']) + ",processes=" + str(metric['processes']) + ",cpuprio=" + str(metric['cpuprio']) + ",hddprio=" + str(metric['hddprio']))
      # metrics with only one level inside dictionary
      for onelevel in ["mem", "swap", "cpu", "blkio"]:
        metricarr = []
        for key, value in metric[onelevel].iteritems():
          metricarr.append(key + "=" + str(value))
	# output definition for single metric
        output.append(header + ",metric=" + onelevel + " " + ','.join(metricarr))
      # metrics with two levels inside dictionary
      for twolevel in ["net", "disk"]:
        for key, value in metric[twolevel].iteritems():
          metricarr = []
          for m,v in value.iteritems():
            metricarr.append(str(m) + "=" + str(v))
          output.append(header + ",metric=" + twolevel + ",dev=" + key  + " " + ','.join(metricarr))
    else:
      # if container is not running, we will send only status metric
      output.append(header + ",metric=status running=" + str(metric['running']))

# loop for master metrics
for metric, value in globalmetrics.iteritems():
    header = "lxd,type=master"
    # metrics with only one leddvel inside dictionary
    metricarr = []
    for key, value in value.iteritems():
      metricarr.append(key + "=" + str(value))
    output.append(header + ",metric=" + metric + " " + ','.join(metricarr))

print '\n'.join(output)

try:
    sys.stdout.close()
except:
    pass
try:
    sys.stderr.close()
except:
    pass
