""" This modules contains netCDF related functions. The functions
in this module typically have a pointer to netCDF variable(s) as
an argument."""

import numpy.ma as ma
import netCDF4
import math
import scipy.constants


def folding_velo(vrs, freq):
    """Returns radar folding velocity.

    Args:
        vrs (dict): Radar variables.
        freq (float): Rardar frequency (GHz).

    Returns:
        float: Radar folding velocity (m/s).

    Raises:
        KeyError:
            No 'NyquistVelocity' or 'prf' in
            radar variables.

    """
    if 'NyquistVelocity' in vrs:
        nyq = vrs['NyquistVelocity'][:]
    elif 'prf' in vrs:
        nyq = vrs['prf'][:] * scipy.constants.c / (4 * freq)
    else:
        raise KeyError("Can't find or compute folding velocity!")
    return math.pi / nyq


def findkey(vrs, possible_fields):
    """Finds first matching key from several possible.

    Args:
        vrs (dict): Dictionary or other
            iterable containing strings.
        fields (tuple): List of possible strings to be
            searched.

    Returns:
        str: First matching key.

    Examples:
        >>> x = {'abc':1, 'bac':2, 'cba':3}
        >>> ncf.findkey(x, ('bac', 'cba'))
            'bac'

        The order of the keys to be searched is defaining
        the return value if there are several matching strings:

        >>> ncf.findkey(x, ('cba', 'bac'))
            'cba'

    """
    for field in possible_fields:
        if field in vrs:
            return field
    return None


def radar_freq(vrs):
    """ Returns frequency of radar.

    Args:
        vrs (dict): Radar variables.

    Returns:
        float: Frequency or radar.

    Raises:
        KeyError: No frequency in the radar file.
        ValueError: Invalid frequency value.

    """
    freq_key = findkey(vrs, ('radar_frequency', 'frequency'))
    if not freq_key:
        raise KeyError('Missing frequency, check your radar file.')
    freq = vrs[freq_key][:]
    assert ma.count(freq) == 1, 'Multiple frequencies, not a radar file?'
    try:
        wl_band(freq)
    except ValueError as error:
        raise error
    return float(freq)


def wl_band(freq):
    """ Returns integer that corresponds to the radar wavelength.

    Args:
        freq (float): Radar frequency (GHz).

    Returns:
        int: Integer corresponding to freqeuency. Possible return
        values are 0 (~35.5 GHz) and 1 (~94 GHz).

    Raises:
        ValueError: Not supported frequency.

    """
    if 30 < freq < 40:
        return 0
    elif 90 < freq < 100:
        return 1
    else:
        raise ValueError('Only 35 and 94 GHz radars supported.')


def km2m(var):
    """ Converts km to m.

    Read input and convert it to from km to m. The input must
    have 'units' attribute set to 'km' to trigger the conversion.

    Args:
        var: NetCDF4 variable.

    Returns:
        array_like: Altitude converted to km.

    """
    alt = var[:]
    if var.units == 'km':
        alt = alt*1000
    return alt


def m2km(var):
    """ Converts m to km.

    Read Input and convert it to from m -> km. The input must
    have 'units' attribute set to 'm' to trigger the conversion.

    Args:
        var: NetCDF4 variable.

    Returns:
        array_like: Altitude converted to m.

    """
    alt = var[:]
    if var.units == 'm':
        alt = alt/1000
    return alt
