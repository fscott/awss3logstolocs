#!/usr/bin/python
#
# Copyright (c) 2015 Franklin Scott
# http://www.franklinscott.com/
#
# This work is licensed under the Creative Commons Attribution-ShareAlike 3.0 International License. 
# To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/3.0/ 
# or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
# This script uses the GeoLite2 data created by MaxMind, available from http://www.maxmind.com.
#
# The AWS server access log format is available here:
# http://docs.aws.amazon.com/AmazonS3/latest/dev/LogFormat.html

import csv
import sys
import os
import re
import time
import datetime
import subprocess
import argparse

class AWSLog:
    # More to add in the future depending on what parsers seem useful
    def __init__(self):
        self.date_time = ''
        self.ip = ''
        self.user_agent = ''
        self.log_filename = ''
        self.location_map = ''
        self.matched_ip = ''

usage = "usage: /.%(prog)s [options] Given a file with a list of ip addresses or a folder with aws s3 logs, print locations from the free Maxmind GeoLite2 databases."
parser = argparse.ArgumentParser(usage=usage)

parser.add_argument("-i", action="store", default='GeoLite2-City-Blocks-IPv4.csv', help="name of ip addresses csv file (default: %(default)s)")
parser.add_argument("-l", action="store", default='GeoLite2-City-Locations-en.csv', help="name of city locations csv file (default: %(default)s)")
parser.add_argument("-f", action="store", default='', help="name of file containing ip addresses")
parser.add_argument("-o", action="store", default='', help="name of output file")
parser.add_argument("-s3", action="store", default='', help="name of s3 bucket with logging enabled")
parser.add_argument("-logpath", action="store", default='root', help="name the local path to logs (default: %(default)s)")
parser.add_argument("-skips3", dest="skips3", action="store_true")
parser.add_argument("-s", action="store", default='1900-01-01', help="start date of logs(YYYY-MM-DD)") # Need to validate these
parser.add_argument("-e", action="store", default=time.strftime('%Y-%m-%d'), help="end date of logs (YYYY-MM-DD) (default: %(default)s)")
parser.add_argument("-today", action="store_true", help="just look at today's logs")
parser.add_argument("-all", action="store_true", help="download all the available logs and process")
parser.add_argument("-nobots", action="store_true", help="ignore apparent bots")


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
path = './%s/' % options.logpath #For logpath to be some current directory

def get_candidates(ip, ips_to_locs):
    short_ip = ip[:ip.rfind('.')]
    candidates = {}
    for x in ips_to_locs:
        lastp = x.rfind('.')
        shortx = x[:lastp]
        templ = []
        if short_ip == shortx:
            if shortx in candidates:
                templ = candidates[shortx]
            templ.append(x[lastp+1:])
            candidates[shortx] = templ
    return candidates

def map_your_ips(your_logs):
    ips_to_locs, locs_to_places = open_csv_files()
    output = []
    all = len(your_logs)
    curr = 0
    for log in your_logs:
        print 'Processing %s out of %s' % (curr,all)
        curr += 1
        candidates = get_candidates(log.ip, ips_to_locs)
        ip_end = log.ip[log.ip.rfind('.')+1:]
        other_ends = []

        if len(candidates) > 0:
            only_candidate = ''
            for key in candidates:       
                only_candidate = key
                if ip_end in candidates[key]:
                    full = '%s.%s' % (key, ip_end)
                    log.matched_ip = full
                    log.location_map = '%s: %s %s %s (%s)' % (log.filename, log.ip.strip(), log.matched_ip, locs_to_places[ips_to_locs[full]], log.user_agent)
                    log.location_map.strip()                
                else:
                    if len(candidates) == 1:
                        for x in candidates[key]:
                            other_ends.append(x)
                    else:
                        print 'More than one candidate. Could be bad cvs data.'
            
            if log.location_map == '':
                best_end = min(other_ends, key=lambda x:abs(int(x)-int(ip_end)))
                full = '%s.%s' % (only_candidate, best_end)
                log.matched_ip = full
                log.location_map = '%s: %s %s %s (%s)' % (log.filename, log.ip.strip(), log.matched_ip, locs_to_places[ips_to_locs[full]], log.user_agent)
                log.location_map.strip() 

        if log.location_map == '':
            log.location_map = '%s: No location match for %s (%s)' % (log.filename, log.ip.strip(), log.user_agent)
            print log.filename + " " + log.ip
    return your_logs

def get_ip_from_s3_log(line):
    p = re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", line)
    return p.group()

def get_User_Agent_from_s3_log(line):
    # This seems to work, although I can't guarantee it.
    end = line.rfind(')')
    begin = line.rfind(' \"',0, end) 
    return line[begin+1:end]
        

def log_in_range(filename):
    if only_today and today in filename:
        return True
    elif not only_today:
        try:
            logdate = filename[0:10]
            logdate = datetime.datetime.strptime(logdate, "%Y-%m-%d")
            if start <= logdate <= end:
                return True    
        except ValueError:
            return False
        return False
    else:
        return False

def get_ips_from_logs(path_to_logs, your_logs):    
    for filename in os.listdir(path_to_logs):
        if 'DS_Store' not in filename and log_in_range(filename):
            with open(path_to_logs + filename) as f:
                log = AWSLog()
                log.filename = filename
                t = f.readlines()
                try:
                    log.ip = get_ip_from_s3_log(t[0])
                    log.user_agent = get_User_Agent_from_s3_log(t[0])
                    if 'bot' in log.user_agent and options.nobots:
                        print 'Skipping %s because it looks like a bot.' % (log.filename)
                    else:
                        your_logs.append(log)  
                except AttributeError:
                    print filename + ' is an invalid file.'
    return your_logs

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
        trim = x[0].rfind('/')
        ip = x[0][:trim]
        ips_to_locs[ip]=x[1]
    
    locs_to_places = {}
    for y in locs:
        loc_data = [y[5],y[7],y[8],y[9],y[10],y[11],y[12]]
        for datum in loc_data:
            if len(datum) < 1:
                loc_data.remove(datum)
        place = ' '.join(loc_data)
        locs_to_places[y[0]] = place  
    return ips_to_locs, locs_to_places

def write_results(your_logs):
    if len(options.o) > 1:
        with open(options.o, 'w') as outfile:
            for log in your_logs:
                outfile.write(log.location_map+'\n')
        print 'See file %s for output.' % (options.o)
    else:
        for log in your_logs:
            print log.location_map

def get_dates():
    dates = []
    if only_today:
        return today
    d = start
    delta = datetime.timedelta(days=1)
    while d<= end:
        dates.append(d)
        d += delta
    return dates

def main():    
    your_logs = []
    # We're trying to get the IPs.
    
    # If there's an input file with IPs, then check to see whether we have locations for any of them.
    if len(options.f) > 0:
        lines = []
        try:
            with open(options.f) as f3:
                for x in f3:
                    log = AWSLog()
                    log.ip = x
                    your_logs.append(log)
        except IOError:
            print 'No file by that name. Exiting'
            sys.exit(1)
    
    # If we're using s3, download the logs and parse them. Or just skip s3 and parse ones we already have.
    s3success = False
    if len(s3bucket) > 0 and options.skips3 == False:
        if options.all:  
            x = subprocess.call(["aws","s3","cp","s3://logs.%s" % s3bucket, options.logpath, "--recursive"],stderr=subprocess.STDOUT)
        elif only_today:
            ob = ("aws","s3","cp","s3://logs.%s/%s" % (s3bucket,options.logpath), path, "--recursive", "--exclude", '"*"', "--include", '"*%s*"' % today)
            comm = ' '.join(ob)
            x = subprocess.Popen(comm, shell=True,stderr=subprocess.STDOUT)            
            x.wait()
            if x.returncode ==0:
                s3success = True
            else:
                s3success = False
                print "There was some problem downloading the logs. Returncode %s" % (x.returncode)    
        else:
            dates = get_dates()
            for y in dates:
                ob = ("aws","s3","cp","s3://logs.%s/%s" % (s3bucket,options.logpath), path, "--recursive", "--exclude", '"*"', "--include", '"*%s*"' % y.strftime("%Y-%m-%d"))
                comm = ' '.join(ob)
                x = subprocess.Popen(comm, shell=True,stderr=subprocess.STDOUT)            
                x.wait()
                if x.returncode ==0:
                    s3success = True
                else:
                    s3success = False
                    print "There was some problem downloading the logs. Returncode %s" % (x.returncode)
        if x == 0:
            s3success = True #for test
    
    if s3success or options.skips3:
        your_logs = get_ips_from_logs(path, your_logs)
                 
    your_logs = map_your_ips(your_logs)
    write_results(your_logs)

if __name__ == "__main__":
    main()
