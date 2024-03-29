#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from ._from_sv import theils_u, theils_sym_u, correlation_ratio
from .utils import split_col_by_type
from scipy.stats import pearsonr
from itertools import combinations
from enum import Enum
import pandas as pd
import numpy as np

def _make_finite(df, col1, col2, col1_numeric, col2_numeric,
                method='mask', replace_value=0):
    """
    Handles NaN values and infinity (if numeric) and returns the two
    columns with valid values only.
    
    Arguments:
        df: The DataFrame.
        col1: Name of the first columns.
        col2: Name of the second column.
        col1_numeric: Whether col1 is to be treated as numeric.
        col2_numeric: Whether col2 is to be treated as numeric.
        method: 'mask' to drop the rows where at least one value is problematic.
                'replace' to replace the problematic values with replace_value.
        replace_value: The value to replace with when method is 'replace'.
    """
    
    if col1_numeric:
        col1_mask = np.isfinite(df[col1])
    else:
        col1_mask = ~pd.isnull(df[col1])
        
    if col2_numeric:
        col2_mask = np.isfinite(df[col2])
    else:
        col2_mask = ~pd.isnull(df[col2])

    if method == 'mask':
        index = np.where(np.logical_and(col1_mask, col2_mask))
        x = df[col1].values[index]
        y = df[col2].values[index]
    elif method == 'replace':
        x = df[col1].values.copy()
        y = df[col2].values.copy()
        x[~col1_mask] = replace_value
        y[~col2_mask] = replace_value
    else:
        raise ValueError("Unknown method '{}'.".format(method))

    return x, y

def _num_cat_select(df, categorical_inputs=None, numeric_inputs=None):
    """
    Splits columns into categorical and numeric.

    Returns df_sel, categorical_inputs, numeric_inputs, where the last two
    items are the assignments of columns as categorical or numeric and df_sel
    is the filtered out version of the input dataframe, which only contains
    columns categorical_inputs $\cup$ numeric_inputs.

    Arguments:
        df: The dataframe.
        categorical_inputs: Names of the columns that hold numeric inputs.
            Defaults to None, which is the same as categorical_inputs=[].
            If 'auto', the columns are determined automatically using
            split_col_by_type.
        numeric_inputs: Names of the columns that hold numeric inputs.
            Defaults to None, i.e. all columns with numeric data types
            should be used, except those listed in categorical_inputs.

            If 'auto', the behaviour is the same as numeric_inputs=None.

            If numeric_inputs is not None and there are columns that are
            marked as neither categorical, nor numeric, they will be dropped.
            If a column is listed as both numeric and categorical, it
            is processed as numeric.
    """
    if categorical_inputs is None:
        categorical_inputs = []
    elif categorical_inputs == 'auto':
        categorical_inputs = None

    if numeric_inputs is 'auto':
        numeric_inputs = None

    if categorical_inputs is None and numeric_inputs is None:
        categorical_inputs, numeric_inputs, _, _ = split_col_by_type(df)
    elif categorical_inputs is None:
        tmp_cat, _, _, _ = split_col_by_type(df)
        categorical_inputs = set(tmp_cat) - set(numeric_inputs)
    elif numeric_inputs is None:
        _, tmp_num, _, _ = split_col_by_type(df)
        tmp_num = set(tmp_num) | set(df.select_dtypes(np.number).columns)
        numeric_inputs = set(tmp_num) - set(categorical_inputs)
        
    df_sel = df[df.columns.intersection(set(categorical_inputs) | set(numeric_inputs))]
    return df_sel, categorical_inputs, numeric_inputs

class CorrType(Enum):
    """
    An enum expressing the correlation type:
        * num_vs_num: numeric vs. numeric;
        * num_vs_cat: numeric vs. categorical;
        * cat_vs_num: categorical vs. numeric;
        * cat_vs_cat: categorical vs. categorical.
    """
    num_vs_num = 0
    num_vs_cat = 1
    cat_vs_num = 2
    cat_vs_cat = 3

def corr(
    df, categorical_inputs=None, numeric_inputs=None,
    corr_method=None, nan_strategy='mask', nan_replace_value=0,
    return_corr_types=False, sym_u=False
):
    """
    A routine that computes associations between pairs of variables
    using a recipe derived from SweetViz:
    * Correlations for numeric vs. numeric;
    * Uncertainty coefficient for categorical vs. categorical,
        i.e. Theil's U(row | column);
    * Correlation ratio for categorical vs. numeric.
    
    Returns two DataFrames: the first hold the association values and
    the second holds the p-values for the numeric vs. numeric correlations.
    For the other types of associations, it holds zeros.
    
    Arguments:
        df: The dataframe to compute associations on.
        categorical_inputs: Names of the columns that hold numeric inputs.
            Defaults to None, i.e. no categorical inputs.
        numeric_inputs: Names of the columns that hold numeric inputs.
            Defaults to None, i.e. all columns with numeric data types
            should be used, except those listed in categorical_inputs.
            If numeric_inputs is not None and there are columns that are
            neither categorical, nor numeric, they will be dropped.
            If a column is listed as both numeric and categorical, it
            is processed as numeric.
        corr_method: The correlation method. Defaults to pearsonr.
        nan_strategy: Specifies how to handle NaNs (and infinity for numeric
            inputs):
            * "mask": remove rows that contain a NaN before the computation;
            * "replace": replace the NaNs with nan_replace_value;
        nan_replace_value: The value to replace NaNs with when nan_strategy is
            "replace". Defaults to 0.
        return_corr_types: Specifies whether to also return a correlation
            types dataframe. If true, a dataframe of CorrType values is
            returned as the third element of the return tuple.
        sym_u: If True, the symmetric variant of the uncertainty 
            coefficient is used instead of the basic asymmetric variant.
            Defaults to False.
    """
    if corr_method is None:
        corr_method = pearsonr

    df_sel, categorical_inputs, numeric_inputs = _num_cat_select(
        df, categorical_inputs, numeric_inputs
    )
    
    df_r = pd.DataFrame(np.ones([df_sel.shape[1], df_sel.shape[1]]), columns=df_sel.columns, index=df_sel.columns)
    df_p = pd.DataFrame(np.zeros([df_sel.shape[1], df_sel.shape[1]]), columns=df_sel.columns, index=df_sel.columns)
    df_ct = pd.DataFrame(np.zeros([df_sel.shape[1], df_sel.shape[1]]), columns=df_sel.columns, index=df_sel.columns)
        
    for col1, col2 in combinations(df_sel.columns, 2):        
        if col1 in numeric_inputs:
            if col2 in numeric_inputs:
                # numeric vs. numeric
                x, y = _make_finite(
                    df, col1, col2,
                    col1_numeric=True, col2_numeric=True,
                    method=nan_strategy, replace_value=nan_replace_value
                )
                r, p = corr_method(x, y)
                df_r.loc[col1, col2] = r
                df_r.loc[col2, col1] = r
                df_p.loc[col1, col2] = p
                df_p.loc[col2, col1] = p
                df_ct.loc[col1, col2] = CorrType.num_vs_num
                df_ct.loc[col2, col1] = CorrType.num_vs_num
            else:
                # numeric vs. categorical
                x, y = _make_finite(
                    df, col1, col2,
                    col1_numeric=True, col2_numeric=False,
                    method=nan_strategy, replace_value=nan_replace_value
                )
                r, p = correlation_ratio(y, x), 0.0                
                df_r.loc[col1, col2] = r
                df_r.loc[col2, col1] = r
                df_p.loc[col1, col2] = p
                df_p.loc[col2, col1] = p
                df_ct.loc[col1, col2] = CorrType.num_vs_cat
                df_ct.loc[col2, col1] = CorrType.num_vs_cat
        else:
            if col2 in numeric_inputs:
                # categorical vs. numeric
                x, y = _make_finite(
                    df, col1, col2,
                    col1_numeric=False, col2_numeric=True,
                    method=nan_strategy, replace_value=nan_replace_value
                )
                r, p = correlation_ratio(x, y), 0.0                
                df_r.loc[col1, col2] = r
                df_r.loc[col2, col1] = r
                df_p.loc[col1, col2] = p
                df_p.loc[col2, col1] = p
                df_ct.loc[col1, col2] = CorrType.cat_vs_num
                df_ct.loc[col2, col1] = CorrType.cat_vs_num
            else:
                # categorical vs. categorical
                x, y = _make_finite(
                    df, col1, col2,
                    col1_numeric=False, col2_numeric=False,
                    method=nan_strategy, replace_value=nan_replace_value
                )

                if sym_u:
                    u = theils_sym_u(x, y)
                    df_r.loc[col1, col2] = u
                    df_r.loc[col2, col1] = u
                else:
                    df_r.loc[col1, col2] = theils_u(x, y)
                    df_r.loc[col2, col1] = theils_u(y, x)

                df_p.loc[col1, col2] = 0.0
                df_p.loc[col2, col1] = 0.0
                df_ct.loc[col1, col2] = CorrType.cat_vs_cat
                df_ct.loc[col2, col1] = CorrType.cat_vs_cat
 
    if return_corr_types:
        return df_r, df_p, df_ct
    else:
        return df_r, df_p
 