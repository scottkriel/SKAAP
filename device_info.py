#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 25 22:49:16 2021
@author: Scott Kriel
Description: Script to fetch info on SDR device
"""
import simplesoapy, textwrap, os

def wrap(text, indent='    '):
    """Wrap text to terminal width with default indentation"""
    wrapper = textwrap.TextWrapper(
        width=int(os.environ.get('COLUMNS', 80)),
        initial_indent=indent,
        subsequent_indent=indent
    )
    return '\n'.join(wrapper.wrap(text))

def device_info(soapy_args=''):
    """Returns info about selected SoapySDR device"""
    text = []
    try:
        device = simplesoapy.SoapyDevice(soapy_args)
        text.append('Selected device: {}'.format(device.hardware))
        text.append('  Available amplification elements:')
        text.append('    {}'.format(', '.join(device.list_gains())))
        text.append('  Allowed gain range [dB]:')
        text.append('    {:.2f} - {:.2f}'.format(*device.get_gain_range()))
        text.append('  Allowed frequency range [MHz]:')
        text.append('    {:.2f} - {:.2f}'.format(*[x / 1e6 for x in device.get_frequency_range()]))
        text.append('  Allowed sample rates [MHz]:')
        rates = []
        for r in device.list_sample_rates():
            if r[0] == r[1]:
                rates.append('{:.2f}'.format(r[0] / 1e6))
            else:
                rates.append('{:.2f} - {:.2f}'.format(r[0] / 1e6, r[1] / 1e6))
        text.append(wrap(', '.join(rates)))
    except RuntimeError:
        device = None
        text.append('No devices found!')
    return (device, '\n'.join(text))

def main():
    device, device_text = device_info
    print(device_text)
if __name__ == '__main__':
    main()
