Python script for gathering metrics of containers on lxd host.


Script is periodically triggered by telegraf and gathered metrics are sent to
influxdb (and/or another metricsdb, based on telegraf configuration).


grafana_dashboards contains example dashbords which using gathered metrics.


This is still WORK IN PROGRESS (or proof of concept maybe).


I'm testing this on Ubuntu LTS 16.04 with LXD version `2.20-0ubuntu4~16.04.1~ppa1`, kernel `4.10.0-40-generic`.


Howto make it work (ubuntu server, for other distro use appropriate tools):

0. install lxd server https://linuxcontainers.org/lxd/introduction/ (i have spotted that this script not working with snap version of LXD - use PPA or Backports)
1. install telegraf https://docs.influxdata.com/telegraf/v1.4/introduction/installation/
2. install influxdb https://docs.influxdata.com/influxdb/v1.3/introduction/installation/
3. install grafana http://docs.grafana.org/installation/debian/
4. configure telegraf to use influxdb (configure the running period for telegraf - default is 10s which should be too often (and may broke things))
5. copy lxd.conf to /etc/telegraf/telegraf.d/
6. copy sudoers telegraf to /etc/sudoers.d/
7. copy lxd-telegraf-stats.py to /usr/local/sbin/ and chmod +x it.
8. install additional python modules: apt-get install python-ws4py python-pylxd (maybe others? look at errors if something missing)
9. try to run script - output should be like: 
```
/usr/local/sbin/lxd-telegraf-stats.py
lxd,type=container,hostname=master-666,name=master,instance=666,metric=status running=1,processes=27,cpuprio=1024,hddprio=500
lxd,type=container,hostname=master-666,name=master,instance=666,metric=mem usage=64884736,usage_pct=3,limit=2147483648,peak=67051520
lxd,type=container,hostname=master-666,name=master,instance=666,metric=swap usage=0,peak=0
lxd,type=container,hostname=master-666,name=master,instance=666,metric=cpu usage=552144742062,limit=2,usage_percpu=276072371031
lxd,type=container,hostname=master-666,name=master,instance=666,metric=blkio bytes_total=31486976,iops_total=779,bytes_write=0,iops_write=0,bytes_read=31486976,iops_read=779
lxd,type=container,hostname=master-666,name=master,instance=666,metric=net,dev=lo pkts_out=788470,bytes_in=68317360,bytes_out=68317360,pkts_in=788470
lxd,type=container,hostname=master-666,name=master,instance=666,metric=net,dev=eth1 pkts_out=182,bytes_in=15541517,bytes_out=12836,pkts_in=182031
lxd,type=container,hostname=master-666,name=master,instance=666,metric=net,dev=vxlan pkts_out=2095146,bytes_in=40770984,bytes_out=85283645,pkts_in=575666
lxd,type=container,hostname=master-666,name=master,instance=666,metric=net,dev=eth0 pkts_out=2118158,bytes_in=97459691,bytes_out=220339657,pkts_in=677739
lxd,type=container,hostname=master-666,name=master,instance=666,metric=disk,dev=tmp usage=0,usage_pct=0,limit=536870912
lxd,type=container,hostname=master-666,name=master,instance=666,metric=disk,dev=root usage=138584064,usage_pct=1,limit=10737418240
lxd,type=container,hostname=logger-666,name=logger,instance=666,metric=status running=1,processes=16,cpuprio=1024,hddprio=500
lxd,type=container,hostname=logger-666,name=logger,instance=666,metric=mem usage=47546368,usage_pct=2,limit=2147483648,peak=50176000
lxd,type=container,hostname=logger-666,name=logger,instance=666,metric=swap usage=0,peak=0
lxd,type=container,hostname=logger-666,name=logger,instance=666,metric=cpu usage=307662859002,limit=2,usage_percpu=153831429501
lxd,type=container,hostname=logger-666,name=logger,instance=666,metric=blkio bytes_total=29099008,iops_total=840,bytes_write=0,iops_write=0,bytes_read=29099008,iops_read=840
lxd,type=container,hostname=logger-666,name=logger,instance=666,metric=net,dev=lo pkts_out=0,bytes_in=0,bytes_out=0,pkts_in=0
lxd,type=container,hostname=logger-666,name=logger,instance=666,metric=net,dev=vxlan pkts_out=10998,bytes_in=32260729,bytes_out=308352,pkts_in=1084500
lxd,type=container,hostname=logger-666,name=logger,instance=666,metric=net,dev=eth0 pkts_out=32390,bytes_in=121446118,bytes_out=1910852,pkts_in=1184950
lxd,type=container,hostname=logger-666,name=logger,instance=666,metric=disk,dev=tmp usage=0,usage_pct=0,limit=536870912
lxd,type=container,hostname=logger-666,name=logger,instance=666,metric=disk,dev=root usage=18042880,usage_pct=0,limit=10737418240
lxd,type=master,metric=mem total=16812589056,given=25402523648,used=691441664,given_pct=151,used_pct=4
lxd,type=master,metric=other live=1
lxd,type=master,metric=hdd total=1990116046274,given=2033065719234,used=316979200,given_pct=102,used_pct=0
lxd,type=master,metric=cpu given=24,total=16
lxd,type=master,metric=containers running=5,total=6,stopped=1,notrunning=1
```
10. restart telegraf: systemctl restart telegraf.service (you should test the gathering with telegraf --test command)
11. login to your grafana and import attached dashboards from grafana_dashboards
12. edit/tweak settings to make it work
13. do not let your eyeballs pop out!
14. maybe i'm missed something, so look at your logs if something went wrong.



```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!!                                   DISCLAIMER:                                   !!!
!!! I'm not a programmer - so .py script is probably very ugly - you've been warned !!!
!!!      No (or almost no) sanity checks, ugly written (can't to call it) code      !!!
!!!    I'm not responsible for any eyeball explosion, use this on your own risk     !!!
!!!                                       :wq                                       !!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

ScreenShot: 

![alt text][screenshot]

[screenshot]: https://raw.githubusercontent.com/wociscz/lxd-telegraf-stats/master/screenshots/Screenshot-2017-11-24%20Grafana%20-%20Instance%20detail.png "Instance Detail"

