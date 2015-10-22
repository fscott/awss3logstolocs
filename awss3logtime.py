#!/usr/bin/python
#
# Copyright (c) 2015 Franklin Scott
# http://www.franklinscott.com/
#
# This work is licensed under the Creative Commons Attribution-ShareAlike 3.0 International License. 
# To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/3.0/ 
# or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
# This script uses the GeoLite2 data created by MaxMind, available from http://www.maxmind.com.

import csv
import sys
import os
import re
import time
import datetime
import subprocess
import argparse

usage = "usage: /.%(prog)s [options] Given a file with a list of ip addresses or a folder with aws s3 logs, print locations from the free Maxmind GeoLite2 databases."
parser = argparse.ArgumentParser(usage=usage)

parser.add_argument("-i", action="store", default='GeoLite2-City-Blocks-IPv4.csv', help="name of ip addresses csv file (default: %(default)s)")
parser.add_argument("-l", action="store", default='GeoLite2-City-Locations-en.csv', help="name of city locations csv file (default: %(default)s)")
parser.add_argument("-f", action="store", default='', help="name of file containing ip addresses")
parser.add_argument("-o", action="store", default='', help="name of output file")
parser.add_argument("-s3", action="store", default='', help="name of s3 bucket with logging enabled")
parser.add_argument("-logpath", action="store", default='./root/', help="name the local path to logs (default: %(default)s)")
parser.add_argument("-skips3", dest="skips3", action="store_true")
parser.add_argument("-s", action="store", default='1900-01-01', help="start date of logs(YYYY-MM-DD)") # Need to validate these
parser.add_argument("-e", action="store", default=time.strftime('%Y-%m-%d'), help="end date of logs (YYYY-MM-DD) (default: %(default)s)")
parser.add_argument("-today", action="store_true", help="look at today's logs")


options = parser.parse_args()
s3bucket = options.s3
today = time.strftime('%Y-%m-%d')
only_today = options.today
s = options.s
e = options.e
try:
    start = datetime.datetime.strptime(s, "%Y-%m-%d")
    if e != today:
        end = datetime.datetime.strptime(e, "%Y-%m-%d")
    else:
        end = datetime.datetime.strptime(today, "%Y-%m-%d")
except ValueError:
    print "Dates are not in correct format. Exiting..."
    sys.exit(1)

def map_your_ips(your_ips):
    ips_to_locs, locs_to_places = open_csv_files()
    output = []
    all = len(your_ips)
    curr = 0
    for line in your_ips:
        print 'Processing %s out of %s' % (curr,all)
        curr += 1
        for x in ips_to_locs: 
            if x in line:
                val = ips_to_locs[x]
                try:
                    output.append(line.strip() + ' ' + locs_to_places[val])
                except KeyError:
                    output.append("No key for " + x)
    return output

def get_ip_from_s3_log(line):
    p = re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", line)
    return p.group()

def log_in_range(filename):
    if only_today and today in filename:
        return True
    try:
        logdate = filename[0:10]
        logdate = datetime.datetime.strptime(logdate, "%Y-%m-%d")
        if start <= logdate <= end:
            return True    
    except ValueError:
        return False
    return False

def get_ips_from_logs(path_to_logs, your_ips):    
    for filename in os.listdir(path_to_logs):
        if 'DS_Store' not in filename and log_in_range(filename):
            with open(path_to_logs + filename) as f:
                t = f.readlines()
                try:
                    your_ips.append(get_ip_from_s3_log(t[0]))
                except AttributeError:
                    print filename + ' is an invalid file.'
    return your_ips

def open_csv_files():
    ips = []
    locs = []          
    try:
        with open(options.i) as f:
            addresses = csv.reader(f)
            for row in addresses:
                ips.append(row)
        
        with open(options.l) as f2:
            locations = csv.reader(f2)
            for row in locations:
        	    locs.append(row)
    except IOError:
        print "Unable to find csv files. Exiting..."
        sys.exit(1)
    
    ips_to_locs = {}
    for x in ips:
        trim = x[0].rfind('.')
        ip = x[0][:trim]
        ips_to_locs[ip]=x[1]
    
    locs_to_places = {}
    for y in locs:
        l = [y[5],y[7],y[8],y[9],y[10],y[11],y[12]]
        for thing in l:
            if len(thing) < 1:
                l.remove(thing)
        place = ' '.join(l)
        locs_to_places[y[0]] = place  
    return ips_to_locs, locs_to_places

def write_results(output):
    if len(options.o) > 1:
        with open(options.o, 'w') as outfile:
            for x in output:
                outfile.write(x)
        print 'See file %s for output.' % (options.o)
    else:
        for x in output:
            print x

def main():    
    your_ips = []
    # We're trying to get the IPs.
    
    # If there's an input file with IPs, then check to see whether we have locations for any of them.
    if len(options.f) > 0:
        lines = []
        try:
            with open(options.f) as f3:
                your_ips = f3.readlines()
        except IOError:
            print 'No file by that name. Exiting'
            sys.exit(1)
    
    # If we're using s3, download the logs and parse them. Or just skip s3 and parse ones we already have.
    s3success = False
    if len(s3bucket) > 0 and options.skips3 == False:
        if len(start) > 0 or len(end) > 0:  
            # Need to finish this
            x = subprocess.call(["aws","s3","cp","s3://logs.%s" % s3bucket, ".", "--recursive"],stderr=subprocess.STDOUT)
        else:
            x = subprocess.call(["aws","s3","cp","s3://logs.%s" % s3bucket, ".", "--recursive"],stderr=subprocess.STDOUT)
        if x == 0:
            s3success = True #for test
    
    if s3success or options.skips3:
        your_ips = get_ips_from_logs(options.logpath, your_ips)
                 
    output = map_your_ips(your_ips)
    write_results(output)

if __name__ == "__main__":
    main()
