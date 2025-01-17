from co2_diag import _change_log_level, validate_verbose
from co2_diag.formatters.nums import numstr
import numpy as np
import xarray as xr
from typing import Union
import logging


def bin_by_year_and_vertical(x_ds_: xr.Dataset,
                             my_year: int,
                             my_vertical_edges: np.array,
                             n_latitude: int,
                             n_longitude: int,
                             my_verbose=True
                             ) -> xr.Dataset:
    """Bin data onto a 2D grid of year and altitude

    Parameters
    ----------
    x_ds_
    my_year
    my_vertical_edges
    n_latitude
    n_longitude
    my_verbose

    Returns
    -------

    """
    # Data are subset by time.
    temp_ds = by_decimalyear(x_ds_, verbose=my_verbose, start=my_year, end=my_year + 1)

    # Data are binned (using numpy histogram2d function)
    temp_ds = bin3d(temp_ds, verbose=my_verbose,
                    vertical_bin_edges=my_vertical_edges,
                    n_latitude=n_latitude, n_longitude=n_longitude)

    return temp_ds


def binTimeLat(dataset: xr.Dataset,
               n_latitude: int = 10, n_time: int = 10,
               var_name: str = 'co2'
               ) -> tuple:
    """Bin data onto a 2D grid of time and latitude

    Parameters
    ----------
    dataset
    n_latitude
    n_time
    var_name

    Returns
    -------
    A 3-tuple
        zi (co2), y_edges (latitude), x_edges (time)
    """
    time = dataset['time'].astype("float")
    lat = dataset['latitude']
    dat = dataset[var_name]

    # Data are binned onto the grid.
    #   (x & y must be reversed due to row-first indexing.)
    zi, y_edges, x_edges = np.histogram2d(lat.values, time.values,
                                          bins=(n_latitude, n_time), weights=dat.values, normed=False)
    counts, _, _ = np.histogram2d(lat.values, time.values,
                                  bins=(n_latitude, n_time))
    zi = np.ma.masked_equal(zi, 0)

    # Mean is calculated.
    zi = zi / counts
    zi = np.ma.masked_invalid(zi)

    #     print(time)
    #     x_edges = [np.datetime64(datetime.utcfromtimestamp(x)) for x in x_edges]  # convert float times back to np.datetime64

    return zi, y_edges, x_edges


def by_decimalyear(dataset: xr.Dataset,
                   start: float = 2017, end: float = 2018,
                   verbose: bool = False) -> Union[xr.Dataset, None]:
    func_log = logging.getLogger("{0}.{1}".format(__name__, "by_decimalyear"))
    orig_log_level = func_log.level
    if verbose:
        _change_log_level(func_log, verbose)

    # We start with the passed-in dataset.
    orig_shape = dataset['time_decimal'].shape
    keep_mask = np.full(orig_shape, True)
    func_log.debug("Original # data points: %s", numstr(orig_shape[0], 0))

    # The data are subsetted by year.
    keep_mask = keep_mask & (dataset['time_decimal'] >= start)
    keep_mask = keep_mask & (dataset['time_decimal'] < end)
    if not keep_mask.data.any():
        func_log.debug(" -- subset between <start=%f and end=%f> -- NO DATA POINTS",
                       start,
                       end,)
        return None
    ds_year = dataset.where(keep_mask, drop=True)
    ds_year_shape = ds_year['time_decimal'].shape
    func_log.debug(" -- subset between <start=%f and end=%f> -- # data points: %s",
                   start,
                   end,
                   numstr(ds_year_shape[0], 0))

    if verbose:
        _change_log_level(func_log, orig_log_level)

    return ds_year


def by_datetime(dataset: xr.Dataset,
                start: np.datetime64 = np.datetime64('2017-01-01'),
                end: np.datetime64 = np.datetime64('2008-01-01'),
                verbose: Union[str, bool] = False) -> Union[xr.Dataset, None]:
    func_log = logging.getLogger("{0}.{1}".format(__name__, "by_datetime"))
    orig_log_level = func_log.level
    if verbose:
        _change_log_level(func_log, validate_verbose(verbose))

    # We start with the passed-in dataset.
    orig_shape = dataset['time'].shape
    keep_mask = np.full(orig_shape, True)
    func_log.debug("Original # data points: %s", numstr(orig_shape[0], 0))

    # The data are subsetted by year.
    keep_mask = keep_mask & (dataset['time'] >= start)
    keep_mask = keep_mask & (dataset['time'] < end)
    if not keep_mask.data.any():
        func_log.debug(" -- subset between <start=%s and end=%s> -- NO DATA POINTS",
                       start,
                       end,)
        return None
    ds_year = dataset.where(keep_mask, drop=True)
    ds_year_shape = ds_year['time'].shape
    func_log.debug(" -- subset between <start=%s and end=%s> -- # data points: %s",
                   start,
                   end,
                   numstr(ds_year_shape[0], 0))

    if verbose:
        _change_log_level(func_log, orig_log_level)

    return ds_year


def binLonLat(dataset: xr.Dataset,
              n_latitude: int = 10, n_longitude: int = 10,
              var_name: str = 'co2'):
    lon = dataset['longitude']
    lat = dataset['latitude']
    dat = dataset[var_name]

    # Data are binned onto the grid.
    #   (x & y must be reversed due to row-first indexing.)
    zi, y_edges, x_edges = np.histogram2d(lat.values, lon.values,
                                          bins=(n_latitude, n_longitude), weights=dat.values, normed=False)
    counts, _, _ = np.histogram2d(lat.values, lon.values,
                                  bins=(n_latitude, n_longitude))
    zi = np.ma.masked_equal(zi, 0)

    # Mean is calculated.
    zi = zi / counts
    zi = np.ma.masked_invalid(zi)

    return zi, y_edges, x_edges


def bin3d(dataset: xr.Dataset, vertical_bin_edges: np.ndarray,
          n_latitude: int = 10, n_longitude: int = 10, units: str = 'ppm',
          var_name: str = 'co2',
          verbose: bool = True) -> xr.Dataset:
    func_log = logging.getLogger("{0}.{1}".format(__name__, "bin3d"))
    if verbose:
        orig_log_level = func_log.level
        _change_log_level(func_log, logging.DEBUG)

    # We start with the passed-in dataset.
    orig_shape = dataset['time_decimal'].shape
    keep_mask_orig = np.full(orig_shape, True)

    # The vertical bins are defined.
    lvls = vertical_bin_edges
    n_vertical = len(lvls)

    # x_arr = []
    # y_arr = []
    value_arr = []
    lvl_pairs = []
    for i, (l0, l1) in enumerate(zip(lvls, lvls[1:])):
        func_log.debug("-Vertical level %d/%d-", i+1, n_vertical-1)
        lvl_pairs.append([l0, l1])

        # The data are subsetted by altitude.
        keep_mask = keep_mask_orig & (dataset['altitude'] > l0)
        keep_mask = keep_mask & (dataset['altitude'] <= l1)
        func_log.debug(f"  subset # data points: %s", numstr(np.count_nonzero(keep_mask), 0))

        # The data are binned along the x and y directions.
        values, y_edges, x_edges = binLonLat(dataset.where(keep_mask, drop=True),
                                             n_latitude=n_latitude, n_longitude=n_longitude)
        value_arr.append(values)

    # Horizontal centers of each bin are retrieved.
    x_centers = 0.5 * (x_edges[1:] + x_edges[:-1])
    y_centers = 0.5 * (y_edges[1:] + y_edges[:-1])
    vertical_centers = 0.5 * (vertical_bin_edges[1:] + vertical_bin_edges[:-1])

    # xg, yg = np.meshgrid(x_centers, y_centers)
    # x_arr.append(xg)
    # y_arr.append(yg)

    # The python lists are converted to 3d numpy arrays.
    z_arr = np.array(value_arr)
    # x_arr = np.array(x_arr)
    # y_arr = np.array(y_arr)

    func_log.debug("subset data shape: %s", z_arr.shape)
    func_log.debug("\nDone.")

    ds_sub = xr.Dataset({
        var_name: xr.DataArray(
            data=value_arr,
            dims=['vertical', 'lat', 'lon'],
            coords={'vertical': vertical_centers,
                    'lat': y_centers,
                    'lon': x_centers,
                    },
            attrs={
                '_FillValue': -999.9,
                'units': 'units'
            }
        ),
        'vertical_edges': xr.DataArray(data=[[l0, l1] for l0, l1 in zip(vertical_bin_edges, vertical_bin_edges[1:])],
                                       dims=['vertical', 'nbnds'],
                                       coords={'nbnds': [0, 1]}),
        'lat_edges': xr.DataArray(data=[[l0, l1] for l0, l1 in zip(y_edges, y_edges[1:])],
                                  dims=['lat', 'nbnds'],
                                  coords={'nbnds': [0, 1]}),
        'lon_edges': xr.DataArray(data=[[l0, l1] for l0, l1 in zip(x_edges, x_edges[1:])],
                                  dims=['lon', 'nbnds'],
                                  coords={'nbnds': [0, 1]}),
    }
    )
    if verbose:
        _change_log_level(func_log, orig_log_level)
    return ds_sub

# def bin_multiyear(dd)