#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 25 22:49:16 2021
@author: Scott Kriel
Description: Get ambient temperature and humidity within receiver box
"""
import Adafruit_DHT, sys

def main():
    
    if len(sys.argv)==3:
        sensor = sys.argv[1]
        DHT_DATA_PIN = sys.argv[2]
    elif len(sys.argv)==2:
        sensor = sys.argv[1]
        DHT_DATA_PIN = 4
    else:
        sensor = 11
        DHT_DATA_PIN = 4
        
    # Read Temp.
    humidity, temperature = Adafruit_DHT.read_retry(sensor, DHT_DATA_PIN)
    try:
        print('Temp: {0:0.1f} C \nHumidity: {1:0.1f} %'.format(temperature,humidity))
    except:
        print('Could not read Temperature')
  
    
if __name__ == '__main__':
    main()
