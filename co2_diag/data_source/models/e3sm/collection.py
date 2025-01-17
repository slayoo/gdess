from co2_diag import set_verbose, benchmark_recipe
from co2_diag.data_source.models.e3sm.calculation import getPMID
from co2_diag.data_source.multiset import Multiset
from co2_diag.operations.datasetdict import DatasetDict
from co2_diag.operations.time import to_datetimeindex
from co2_diag.operations.convert import co2_kgfrac_to_ppm
from co2_diag.graphics.utils import aesthetic_grid_no_spines, mysavefig
from co2_diag.formatters import append_before_extension
from co2_diag.recipe_parsers import add_shared_arguments_for_recipes, parse_recipe_options
import xarray as xr
import matplotlib.pyplot as plt
from typing import Union
import argparse, logging

_logger = logging.getLogger("{0}.{1}".format(__name__, "loader"))


class Collection(Multiset):
    def __init__(self, verbose: Union[bool, str] = False):
        """Instantiate an E3SM Collection object.

        Parameters
        ----------
        verbose: Union[bool, str], default False
            can be either True, False, or a string for level such as "INFO, DEBUG, etc."
        """
        set_verbose(_logger, verbose)

        super().__init__(verbose=verbose)

    @classmethod
    def _recipe_base(cls,
                     verbose: Union[bool, str] = False,
                     pickle_file: str = None,
                     nc_file: str = None
                     ) -> ('Collection', bool):
        """Create an instance, and either preprocess or load already processed data.

        Parameters
        ----------
        verbose : Union[bool, str], default False
        pickle_file : str, default None
        nc_file : str, default None

        Returns
        -------
        tuple
            Collection
            bool
                Whether datasets were loaded from a pickle file or not. (If not, there is probably more processing needed.)
        """
        # An empty instance is created.
        new_self = cls(verbose=verbose)

        # If a valid filename is provided, datasets are loaded into stepC attribute and this is True,
        # otherwise, this is False.
        loaded_from_pickle_bool = new_self.datasets_from_pickle(filename=pickle_file, replace=True)

        if not loaded_from_pickle_bool:
            # Data are formatted into the basic data structure common to various diagnostics.
            new_self.preprocess(filepath=nc_file)

        return new_self, loaded_from_pickle_bool

    @classmethod
    @benchmark_recipe
    def run_recipe_for_timeseries(cls,
                                  verbose: Union[bool, str] = False,
                                  pickle_file=None,
                                  options: dict = None
                                  ) -> 'Collection':
        """Execute a series of preprocessing steps and generate a diagnostic result.

        Parameters
        ----------
        verbose
            can be either True, False, or a string for level such as "INFO, DEBUG, etc."
        pickle_file : str, default None
            path to pickled datastore
        options : dict
            Contains zero or more of these parameter keys:
                test_data : str
                    path to NetCDF file of E3SM model output
                start_yr : str, default '1960'
                end_yr : str, default None
                lev : int, default is the last value

        Returns
        -------
        Collection object for E3SM that was used to generate the diagnostic
        """
        set_verbose(_logger, verbose)
        opts = parse_recipe_options(options, add_e3sm_collection_args_to_parser)

        new_self, loaded_from_pickle = cls._recipe_base(verbose=verbose,
                                                        pickle_file=pickle_file,
                                                        nc_file=opts.ref_data)
        n_lev = len(new_self.stepB_preprocessed_datasets['main'].lev)  # get last level
        if not opts.lev_index:
            opts.lev_index = n_lev-1

        # --- Apply diagnostic parameters and prep data for plotting ---
        if not loaded_from_pickle:
            _logger.info('Applying selected bounds..')
            new_self.validate_time_options(opts.start_datetime, opts.end_datetime)

            selection = {'time': slice(opts.start_datetime, opts.end_datetime)}
            new_self.stepC_prepped_datasets = new_self.stepB_preprocessed_datasets.queue_selection(**selection,
                                                                                                   inplace=False)
            iselection = {'lev': opts.lev_index}
            new_self.stepC_prepped_datasets.queue_selection(**iselection, isel=True, inplace=True)
            # Spatial mean is calculated, leaving us with a time series.
            new_self.stepC_prepped_datasets.queue_mean(dim=('ncol'), inplace=True)
            # The lazily loaded selections and computations are here actually processed.
            new_self.stepC_prepped_datasets.execute_all(inplace=True)

        # --- Plotting ---
        fig, ax, bbox_artists = new_self.plot_timeseries()
        if opts.figure_savepath:
            mysavefig(fig=fig, plot_save_name=append_before_extension(opts.figure_savepath, 'e3sm_timeseries'),
                      bbox_extra_artists=bbox_artists)

        return new_self

    @staticmethod
    def _preprocess_functions(dataset: xr.Dataset):
        """Run a set of functions on a dataset

        - Set coordinates
        - Sort the time dimension
        - Ensure time is a datetimeindex type
        - Convert CO2 kg/kg to ppm

        Parameters
        ----------
        dataset : xr.Dataset

        Returns
        -------
        An xr.Dataset
        """
        dataset['PMID'] = getPMID(dataset['hyam'], dataset['hybm'], dataset['P0'], dataset['PS'])
        dataset = (dataset
                   .set_coords(['time', 'lat', 'lon', 'PMID'])
                   .sortby(['time'])
                   .pipe(to_datetimeindex)
                   .pipe(co2_kgfrac_to_ppm, co2_var_name='CO2')
                   )
        return dataset

    def preprocess(self, filepath: str) -> None:
        """Set up the dataset that are common to every diagnostic

        Parameters
        ----------
        filepath : str
        """
        _logger.info("Preprocessing...")

        _logger.debug(' Opening the file..')
        self.stepA_original_datasets = DatasetDict({'main': xr.open_dataset(filepath)})
        self.stepB_preprocessed_datasets = self.stepA_original_datasets.copy()

        _logger.debug(' Setting coords, formatting time, converting to ppm..')
        self.stepB_preprocessed_datasets.apply_function_to_all(self._preprocess_functions, inplace=True)

        _logger.info("Preprocessing is done.")

    def plot_timeseries(self) -> (plt.Figure, plt.Axes, tuple):
        """Make timeseries plot of co2 concentrations from the E3SM output

        Requires self.stepC_prepped_datasets attribute with a time dimension.

        Returns
        -------
        matplotlib figure
        matplotlib axis
        tuple
            Extra matplotlib artists used for the bounding box (bbox) when saving a figure
        """
        my_cmap = self.categorical_cmap(nc=1, nsc=1, cmap="tab10")

        fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(8, 4))

        plt.plot(self.stepC_prepped_datasets['main']['time'],
                 self.stepC_prepped_datasets['main']['CO2'],
                 label=f"E3SM simulation", color=my_cmap.colors[0], alpha=0.6)
        #
        ax.set_ylabel('$CO_2$ [ppm]')
        aesthetic_grid_no_spines(ax)
        #
        bbox_artists = ()

        return fig, ax, bbox_artists

    def __repr__(self) -> str:
        """ String representation is built.
        """
        strrep = f"-- E3SM Collection -- \n" \
                 f"Datasets:" \
                 f"\n\t" + \
                 self._original_datasets_list_str() + \
                 f"\n" \
                 f"All attributes:" \
                 f"\n\t" + \
                 '\n\t'.join(self._obj_attributes_list_str())

        return strrep


def add_e3sm_collection_args_to_parser(parser: argparse.ArgumentParser) -> None:
    """Add recipe arguments to a parser object

    Parameters
    ----------
    parser : argparse.ArgumentParser
    """
    add_shared_arguments_for_recipes(parser)
    parser.add_argument('--lev_index', default=None, type=int)
