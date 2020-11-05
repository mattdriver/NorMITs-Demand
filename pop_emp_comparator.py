# -*- coding: utf-8 -*-
"""
    Module to compare the inputs and outputs of the MSOA population and employment data.
"""

##### IMPORTS #####
# Standard imports
import re
import time
from pathlib import Path
from typing import Tuple

# Third party imports
import pandas as pd
import numpy as np

# Local imports
from demand_utilities import utils as du

##### CLASSES #####
class PopEmpComparator:
    """Class to read the input MSOA population (or employment) data and compare it to the output.

    Reads the input values, growth, constraints and type ratios and compares these to the
    output population (or employment) data at various levels of aggregation. Csvs are produced
    with the comparisons for checking.
    """
    ZONE_COL = 'model_zone_id'

    def __init__(self, input_csv: str, growth_csv: str,
                 constraint_csv: str, ratio_csv: str,
                 output_csv: str, data_type: {'population', 'employment'},
                 base_year: str):
        """Reads and checks the csvs required for the comparisons.

        Parameters
        ----------
        input_csv : str
            Path to csv containing the input population (or employment) data for
            the base year at MSOA level.
        growth_csv : str
            Path to the csv containing the input growth values for population (or employment)
            at MSOA level for all output years.
        constraint_csv : str
            Path to the csv containing the input constraints for population (or employment)
            at MSOA level for all output years.
        ratio_csv : str
            Path to the csv containing the ratios between the population (or employment) types
            at MSOA level for all output years.
        output_csv : str
            Path to the output population (or employment) data produced by the
            EFSProductionGenerator (or EFSAttractionGenerator) class at MSOA level.
        data_type : {'population', 'employment'}
            Whether 'population' or 'employment' data is given for the comparison.
        base_year : str
            Base year of the model.

        Raises
        ------
        ValueError
            If the data_type parameter isn't 'population' or 'employment' or the base_year
            isn't found as a column in the output csv.
        """
        # Function to provide information on reading inputs
        def read_print(csv, **kwargs):
            start = time.perf_counter()
            print(f'\tReading "{csv}"', end='')
            df = du.safe_read_csv(csv, **kwargs)
            print(f' - Done in {time.perf_counter() - start:,.1f}s')
            return df

        # Check data_type is allowed and initialise variables for that type
        self.data_type = data_type.lower()
        if self.data_type == 'population':
            ratio_cols = [self.ZONE_COL, 'property_type_id', 'traveller_type_id']
            base_yr_col  = 'base_year_population'
        elif self.data_type == 'employment':
            ratio_cols = [self.ZONE_COL, 'employment_class']
            base_yr_col = 'base_year_workers'
        else:
            raise ValueError('data_type parameter should be "population" or "employment" '
                             f'not "{data_type}"')
        print(f'Initialising {self.data_type.capitalize()} comparisons:')

        # Read the output data and extract years columns
        self.output = read_print(output_csv)
        pat = re.compile(r'\d{4}')
        self.years = [i for i in self.output.columns if pat.match(i.strip())]
        # Check base year is present in output
        self.base_year = base_year
        if str(self.base_year) not in self.years:
            raise ValueError(f'Base year ({self.base_year}) not found in the '
                             f'{self.data_type} output DataFrame.')

        # Read the required columns for input csvs
        self.input_data = read_print(input_csv, skipinitialspace=True)
        self.input_data.rename(columns={base_yr_col: str(self.base_year)}, inplace=True)
        cols = [self.ZONE_COL, *self.years]
        self.growth_data = read_print(growth_csv, skipinitialspace=True, usecols=cols)
        self.constraint_data = read_print(constraint_csv, skipinitialspace=True, usecols=cols)
        self.ratio_data = read_print(ratio_csv, skipinitialspace=True,
                                     usecols=ratio_cols + self.years)

        # Normalise the growth data against the base year
        self.growth_data[self.years] = self.growth_data[self.years].div(
            self.growth_data[str(self.base_year)], axis=0)

        # Initialise output folder path
        self.output_dir = Path(output_csv).parent / f'{data_type} comparisons'.title()
        self.output_dir.mkdir(exist_ok=True)

    def compare_totals(self) -> pd.DataFrame:
        """Compares the input and output column totals and produces a summary of the differences.

        Returns
        -------
        pd.DataFrame
            DataFrame containing differences between the input and output column totals.
        """
        # Calculate totals for each input and output for each year column
        totals = pd.DataFrame({'input total': self.input_data.sum(),
                               'constraint total': self.constraint_data.sum(),
                               'mean growth input': self.growth_data.mean(),
                               'output total': self.output.sum()})
        drop_index = [i for i in totals.index if i not in self.years]
        totals = totals.drop(index=drop_index)
        totals.index.name = 'year'

        # Calculate comparison columns
        totals['constraint difference'] = totals['output total'] - totals['constraint total']
        totals['constraint % difference'] = (totals['output total']
                                             / totals['constraint total']) - 1
        totals['output growth'] = (totals['output total']
                                   / totals.loc[self.base_year, 'output total'])
        totals['growth difference'] = totals['output growth'] - totals['mean growth input']
        return totals

    def compare_msoa_totals(self) -> pd.DataFrame:
        """Compares the input and output values at MSOA level and produces a summary.

        Returns
        -------
        pd.DataFrame
            Differences between the input and output values at MSOA level.
        """
        # Calculate totals for each MSOA on the outputs
        cols = [self.ZONE_COL, *self.years]
        output_msoa = self.output[cols].groupby(self.ZONE_COL, as_index=False).sum()

        # Set index of dataframes to ZONE_COL for concat and rename columns with source
        concat = []
        for nm, df in (('input', self.input_data), ('constraint', self.constraint_data),
                       ('growth', self.growth_data), ('output', output_msoa)):
            df = df.set_index(self.ZONE_COL)
            df.columns = pd.MultiIndex.from_tuples([(i, nm) for i in df.columns])
            concat.append(df)
        msoa_comp = pd.concat(concat, axis=1)

        # Calculate comparison columns
        for yr in self.years:
            msoa_comp[(yr, 'constraint difference')] = (msoa_comp[(yr, 'output')]
                                                        - msoa_comp[(yr, 'constraint')])
            msoa_comp[(yr, 'constraint % difference')] = (msoa_comp[(yr, 'output')]
                                                          / msoa_comp[(yr, 'constraint')]) - 1
            msoa_comp[(yr, 'output growth')] = (msoa_comp[(yr, 'output')]
                                                / msoa_comp[(self.base_year, 'output')])
            msoa_comp[(yr, 'growth difference')] = (msoa_comp[(yr, 'output growth')]
                                                    - msoa_comp[(yr, 'growth')])

        # Sort columns
        return msoa_comp.sort_index(axis=1, level=0, sort_remaining=False)

    def compare_sector_totals(self) -> pd.DataFrame:
        # FIXME Placeholder for sector total comparison
        return pd.DataFrame()

    def ratio_comparison(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Calculates the ratio of types in the output and compares to ratio input.

        The ratio of the outputs is calculated for traveller type (or employment class)
        and summarised at MSOA level and matrix total.

        Returns
        -------
        : pd.DataFrame
            Comparisons between the input and output ratios at MSOA level.
        : pd.DataFrame
            Comparisons between the input and output ratios for column totals with information
            on the number of MSOAs which are the same.
        """
        # Initialise variables dependant on data_type being processed
        if self.data_type == 'population':
            # Calculate total population per MSOA property type
            join_cols = [self.ZONE_COL, 'property_type_id']
            output_totals = self.output.groupby(join_cols, as_index=False).sum()
            class_col = 'traveller_type_id'
            # Precision given in population ratio input
            RATIO_DIFFERENCE = 1E-17
        elif self.data_type == 'employment':
            class_col = 'employment_class'
            join_cols = [self.ZONE_COL]
            # Get the total employment per MSOA from E01 column
            output_totals = self.output.loc[self.output[class_col] == 'E01']
            # Precision given in employment ratio input
            RATIO_DIFFERENCE = 1E-9

        # Join total data to outputs to calculate ratios of outputs
        suff = '_totals'
        output_ratios = self.output.merge(output_totals.drop(columns=class_col), on=join_cols,
                                          how='left', validate='m:m', suffixes=('', suff))
        for yr in self.years:
            output_ratios[yr] = output_ratios[yr] / output_ratios[yr + suff]
            output_ratios.drop(columns=yr + suff, inplace=True)

        # Join input ratios
        output_ratios = output_ratios.merge(self.ratio_data, on=[*join_cols, class_col],
                                            how='left', validate='1:1',
                                            suffixes=('_output', '_input'))
        output_ratios.set_index([*join_cols, class_col], inplace=True)
        # Create multiple levels for column names
        cols = (i.split('_') for i in output_ratios.columns)
        output_ratios.columns = pd.MultiIndex.from_tuples(cols)

        # Create comparison column, checking they're the same within precision given in input
        col_nm = f'within {RATIO_DIFFERENCE}'
        for yr in self.years:
            output_ratios[(yr, 'difference')] = (output_ratios[(yr, 'input')]
                                                    - output_ratios[(yr, 'output')]).abs()
            output_ratios[(yr, col_nm)] = output_ratios[(yr, 'difference')] < RATIO_DIFFERENCE
        output_ratios.sort_index(axis=1, level=0, sort_remaining=False, inplace=True)

        # Function to combine two lists so all items are paired into all unique pairs
        combine_lists = lambda l1, l2: zip(np.repeat(l1, len(l2)), np.tile(l2, len(l1)))
        # Produce summary showing various statistics across all MSOAs
        agg = ['median', 'mean', 'std', 'min', 'max']
        aggregate = {
            **dict.fromkeys(combine_lists(self.years, ['input', 'output']), agg),
            **dict.fromkeys(combine_lists(self.years, ['difference']), ['mean', 'max']),
            **dict.fromkeys(combine_lists(self.years, [col_nm]), ['sum', 'count'])
            }
        group_cols = [i for i in [*join_cols, class_col] if i != self.ZONE_COL]
        total_ratios = output_ratios.groupby(group_cols).agg(aggregate)
        # Calculate percentage of MSOAs that are within the precision given in input
        for yr in self.years:
            total_ratios[(yr, col_nm, '% total')] = (total_ratios[(yr, col_nm, 'sum')]
                                                      / total_ratios[(yr, col_nm, 'count')])
        # Sort and rename columns
        total_ratios.sort_index(axis=1, level=0, sort_remaining=False, inplace=True)
        total_ratios.rename(columns={col_nm: 'MSOAs', 'sum': col_nm, 'count': 'total'},
                            inplace=True)

        return output_ratios, total_ratios

    def write_comparisons(self):
        """Runs each comparison method and writes the output to a csv. """
        print(f'Producing {self.data_type.capitalize()} comparisons:')
        # Comparison methods to run with tuple containing names for return DataFrames
        comparisons = ((self.compare_totals, ('Totals Summary',)),
                       (self.compare_msoa_totals, ('MSOA Totals Comparison',)),
                       (self.compare_sector_totals, ('Sector Totals Comparison',)),
                       (self.ratio_comparison, ('Ratio Comparison MSOA',
                                                'Ratio Comparison Totals')))
        # Run all comparisons and save each DataFrame to a csv
        for func, names in comparisons:
            # Create tuple for dataframes if func only returns one, so it can be looped through
            dataframes = (func(),) if len(names) == 1 else func()
            for nm, df in zip(names, dataframes):
                du.safe_dataframe_to_csv(df, self.output_dir / f'{nm}.csv')
        print(f'\tSaved in: "{self.output_dir}"')
        return

##### FUNCTIONS #####
def test():
    """Tests the PopEmpComparator class on data from previous run of EFS. """
    # Input and output paths hardcoded for testing
    import_loc = Path('Y:/NorMITs Demand/inputs/default')
    output_loc = Path('C:/WSP_Projects/TfN EFS/02 Delivery/00 - EFS Test Run/NorMITs Demand'
                      '/norms/v2_2-EFS_Output/iter2')
    BASE_YEAR = '2018'
    # Population csv files
    population_value_file = "population/base_population_2018.csv"
    population_growth_file = "population/future_population_growth.csv"
    population_constraint_file = "population/future_population_values.csv"
    future_population_ratio_file = "traveller_type/traveller_type_splits.csv"
    population_output_file = 'Productions/MSOA_population.csv'
    # Employment csv files
    worker_value_file = "employment/base_workers_2018.csv"
    worker_growth_file = "employment/future_workers_growth.csv"
    worker_constraint_file = "employment/future_workers_growth_values.csv"
    worker_ratio_file = "employment/future_worker_splits.csv"
    worker_output_file = 'Attractions/MSOA_workers.csv'

    # Compare the population inputs and outputs
    pop_comp = PopEmpComparator(import_loc / population_value_file,
                                import_loc / population_growth_file,
                                import_loc / population_constraint_file,
                                import_loc / future_population_ratio_file,
                                output_loc / population_output_file,
                                'population', BASE_YEAR)
    pop_comp.write_comparisons()
    # Compare the employment inputs and outputs
    emp_comp = PopEmpComparator(import_loc / worker_value_file,
                                import_loc / worker_growth_file,
                                import_loc / worker_constraint_file,
                                import_loc / worker_ratio_file,
                                output_loc / worker_output_file,
                                'employment', BASE_YEAR)
    emp_comp.write_comparisons()

    return


##### MAIN #####
if __name__ == '__main__':
    test()
