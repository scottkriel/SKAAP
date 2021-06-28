#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 25 22:49:16 2021
@author: Scott Kriel
Description: Script to detect connected SDR devices
"""
import simplesoapy


def detect_devices(soapy_args=''):
    """Returns detected SoapySDR devices"""
    devices = simplesoapy.detect_devices(soapy_args, as_string=True)
    text = []
    text.append('Detected SoapySDR devices:')
    if devices:
        for i, d in enumerate(devices):
            text.append('  {}'.format(d))
    else:
        text.append('  No devices found!')
    return (devices, '\n'.join(text))

def main():
    devices, devices_text = detect_devices()
    print(devices)
if __name__ == '__main__':
    main()
        
