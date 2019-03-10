import os
import time
import subprocess as sub
import signal
import argparse
from collections import namedtuple
from operator import itemgetter as iget

import fcntl

PulseGap = namedtuple('PulseGap', 'pulse gap')
PulseGap.__new__.__defaults__ = (0, 0)


def non_block_read(output):
    fd = output.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        return output.read()
    except:
        return ''

def mode2_to_array(mode2_output):
    # Remove first line "Using driver default on device /dev/lirc0"
    raw_codes = mode2_output.split('\n', maxsplit=1)[1]
    # Count number of \n\n
    count = raw_codes.count('\n\n')
    raw_codes = list(map(int, raw_codes.split()))
    sig_len = len(raw_codes) // count
    return [
        raw_codes[(i*sig_len)+1:(i*sig_len)+sig_len]
        for i in range(count)
    ]

def raw_array_to_means(raw_codes_array):
    # TODO: Assert all signals have equal lengths
    if raw_codes_array and \
        not all(len(raw_codes_array[0]) == len(a) for a in raw_codes_array):
        raise ValueError('raw codes have different lengths')
    return [
        sum(map(iget(i), raw_codes_array)) // len(raw_codes_array)
        for i in range(len(raw_codes_array[0]))
    ]

def means_to_pulse_gap_array(mean_codes):
    paired_codes = [
        PulseGap(pulse=mean_codes[i], gap=mean_codes[i+1])
        for i in range(len(mean_codes)-1, 2)
    ]
    paired_codes.append(PulseGap(pulse=mean_codes[-1]))
    return paired_codes

def codes_to_lines(codes, prefix_spaces=2):
    lines = []
    step = 6  # 3 bits, pulse-gap per bit
    for i in range(0, len(codes), step):
        line = ''.join(['{0:>8}'.format(code) for code in codes[i:i+step]])
        lines.append(' '*prefix_spaces + line)
    return '\n'.join(lines)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        'decode.py',
        description='Uses mode2 in LIRC to decode IR signals'
    )
    parser.add_argument(
        '--lirc_device', type=str, default='/dev/lirc0',
        help='LIRC Device name'
    )
    parser.add_argument(
        '--remote', '-r', type=str, required=True,
        help='Name of remote control'
    )
    parser.add_argument(
        '--output_raw', type=str, default='',
        help='Filename for raw mode2 output'
    )
    parser.add_argument(
        '--timeout', type=int, default=3,
        help='IR receiver timeout'
    )
    parser.add_argument(
        'config_file', type=str,
        help='LIRC configuration filename'
    )
    args = parser.parse_args()

    temp_output = 'mode2.temp.out'
    if args.output_raw:
        temp_output = args.output_raw
    if os.path.exists(temp_output):
        os.remove(temp_output)
    command_code_d = {}
    while True:
        command = input('Enter command name (or Enter to quit): ')
        if not command:
            break

        print('Press "{}" on the remote'.format(command))
        print(
            '  Detection will timeout in {}s\n'
            '  (Ctrl+C to halt)'.format(args.timeout)
        )
        temp_output += '.' + command
        cmd = 'mode2 -m -d {} > {}'.format(args.lirc_device,temp_output)
        p = sub.Popen(cmd, shell=True)
        elapsed = 0
        while True:
            try:
                if elapsed == args.timeout:
                    print('{}s'.format(args.timeout))
                    print('Timeout')
                elif elapsed % 1 == 0.0:
                    print('{}..'.format(int(args.timeout-elapsed)), end='')
                time.sleep(0.1)
                elapsed += 0.1
            except KeyboardInterrupt:
                p.send_signal(signal.SIGINT)
                break
            
        with open(temp_output, 'r') as f:
            raw_out = f.read()
        if not args.output_raw:
            os.remove(temp_output)
        if not raw_out:
            raise ValueError(
                'No IR codes detected by mode2. Check gpio_in_pin value.'
            )
        raw_codes_array = mode2_to_array(raw_out)
        
        print('Processing codes...', end=' ')
        mean_codes = raw_array_to_means(raw_codes_array)
        print('Done.')

        command_code_d[command] = mean_codes
        # TODO: Group codes into pulse-gap pairs

    print('Creating LIRCD file...',)
    # Refer to http://www.lirc.org/html/lircd.conf.html
    with open(args.config_file, 'w') as writer:
        # Remote information
        print('begin remote', file=writer)
        print('  name      {}'.format(args.remote), file=writer)
        print('  flags     RAW_CODES', file=writer)
        print('  eps       30', file=writer)  # relative error tolerance in %
        print('  aeps      100', file=writer)  # absolute error tolerance in ms
        print('  ptrail    0', file=writer)  # trailing pulse
        print('  repeat    0 0', file=writer)
        print('  gap       28205', file=writer)  # long space after trailing pulse
        print('  frequency 38000', file=writer)  # frequency in Hz
        # Commands
        print('')
        print('  begin raw_codes\n', file=writer)
        for command, codes in command_code_d.items():
            print('   name {}'.format(command), file=writer)
            print(codes_to_lines(codes, prefix_spaces=3), file=writer)
            print('\n', file=writer)

        print('  end raw_codes\n', file=writer)
        print('end remote', file=writer)
    
    print('LIRCD config file saved to {}'.format(args.config_file))
    print('Done.')

    print('\n---')
    print('Finished.')



# LIRCD File for Haier Aircon
#
 
# begin remote
 
#   name   achaier
#   flags  RAW_CODES
#   eps     30
#   aeps   100
 
#   ptrail   0
#   repeat 0 0
#   gap 28205
 
#   begin raw_codes
    
#     name off
#      3050     3017     3050     4281      599     1677
#       570      557      578     1678      579      686
#       574      586      548     1681      577      561
#       573     1809      574     1682      597     1672
#       575      558      577      688      571      563
#       571      588      547      560      574      690
#       579      554      580      553      603     1693
#       544     1823      570      557      577      582
#       552      555      579     1834      549      559
#       576      557      577      588      567      679
#       580      553      571     1684      574     1682
#       576      689      570      563      572      561
#       573      561      573      691      599     1670
#       578     1678      580      553      571      694
#       576     1679      578     1678      580      579
#       545     1816      577     1685      594     1669
#       579     1677      570      694      576      584
#       550      558      576     1684      574      685
#       574      560      574      559      607      540
#       574      691      578      555      579      554
#       570      563      576      688      576      557
#       578      555      580      554      600      701
#       579     1676      572      562      572     1689
#       569      714      576      557      577     1679
#       579     1677      571      562      604 
