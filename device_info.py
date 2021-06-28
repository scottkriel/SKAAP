#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 25 22:49:16 2021
@author: Scott Kriel
Description: Script to fetch info on SDR device
"""
import simplesoapy

def device_info(soapy_args=''):
    """Returns info about selected SoapySDR device"""
    text = []
    try:
        device = simplesoapy.SoapyDevice(soapy_args)
        text.append('Selected device: {}'.format(device.hardware))
        text.append('  Amplification elements: {}'.format(', '.join(device.list_gains())))
        text.append('  Gain range [dB]: {:.2f} - {:.2f}'.format(*device.get_gain_range()))
        text.append('  Frequency range [MHz]: {:.2f} - {:.2f}'.format(*[x / 1e6 for x in device.get_frequency_range()]))
        rates = []
        for r in device.list_sample_rates():
            if r[0] == r[1]:
                rates.append('{:.2f}'.format(r[0] / 1e6))
            else:
                rates.append('{:.2f} - {:.2f}'.format(r[0] / 1e6, r[1] / 1e6))
        text.append('  Sample rates [MHz]: {}'.format(', '.join(rates)))
    except RuntimeError:
        device = None
        text.append('No devices found!')
    return (device, text)

def main():
    device, device_text = device_info()
    print(device_text)
if __name__ == '__main__':
    main()
