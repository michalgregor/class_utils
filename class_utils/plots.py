#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Optional, Union
from tsmoothie.smoother import _BaseSmoother, LowessSmoother
import matplotlib.patches as patches
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.collections import PatchCollection
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
import numpy as np
from .corr import corr, CorrType
from matplotlib.colors import PowerNorm
from seaborn.matrix import _DendrogramPlotter
from .utils import numpy_crosstab
import pandas as pd
import numbers
import itertools
import math

# Portions of this file (_zaric_heatmap) contain code
# from the following repository:
# https://github.com/fbdesignpro/sweetviz
# and by extension, also the following repository:
# https://github.com/dylan-profiler/heatmaps
#
# The code is licensed under the MIT and the BSD licenses respectively.

# raincloud plots
if sns.__version__ < "0.12.0":
    from ._from_ptitprince import half_violinplot, RainCloud
else:
    from ._from_ptitprince_012 import half_violinplot, RainCloud

def error_histogram(Y_true, Y_predicted, Y_fit_scaling=None,
                    with_error=True, 
                    with_output=True, 
                    with_mae=True, with_mse=False, 
                    error_color='tab:red', output_color='tab:blue',
                    error_kwargs=dict(alpha=0.8, kde=True, linewidth=0,
                                      kde_kws=dict(cut=3)),
                    output_kwargs=dict(alpha=0.4, kde=True, linewidth=0,
                                       kde_kws=dict(cut=3)),
                    mae_kwargs=dict(c='k', ls='--'),
                    mse_kwargs=dict(c='k', ls='--'),
                    standardize_outputs=True, ax=None,
                    num_label_precision=3):
    """
    Plots the error and output histogram.

    Arguments:
        * Y_true: the array of desired outputs;
        * Y_predicted: the array of predicted outputs;
        * Y_fit_scaling: the array to be used to fit the output scaling: if
            None, Y_true is used instead.
    """

    if ax is None:
        ax = plt.gca()

    if Y_fit_scaling is None:
        Y_fit_scaling = Y_true

    if standardize_outputs:
        hist_preproc = StandardScaler()
        hist_preproc.fit(np.asarray(Y_true).reshape(-1, 1))
        Y_true = hist_preproc.transform(np.asarray(Y_true).reshape(-1, 1))
        Y_predicted = hist_preproc.transform(np.asarray(Y_predicted).reshape(-1, 1))

    error = Y_true - Y_predicted

    # we share the same x-axis but create an additional y-axis
    ax1 = ax
    ax2 = ax.twinx()

    if with_output:
        sns.histplot(Y_true.flatten(), label="desired output", ax=ax1,
                     color=output_color, **output_kwargs)
        ax1.set_xlabel('value')
        ax1.set_ylabel('output frequency', color=output_color)
        ax1.tick_params(axis='y', labelcolor=output_color)

    if with_error:
        sns.histplot(error.flatten(), label="error", color=error_color,
            ax=ax2, **error_kwargs)
        ax2.set_ylabel('error frequency', color=error_color)
        ax2.tick_params(axis='y', labelcolor=error_color)

    if with_mae:
        mae = mean_absolute_error(Y_true, Y_predicted)
        plt.axvline(mae, **mae_kwargs)
        plt.annotate(
            "MAE = {}".format(
                np.array2string(np.asarray(mae), precision=num_label_precision)
            ),
            xy=(mae, 0.8),
            xycoords=('data', 'figure fraction'),
            textcoords='offset points', xytext=(5, 0),
            ha='left', va='bottom', color='k'
        )

    if with_mse:
        mse = mean_squared_error(Y_true, Y_predicted)
        plt.axvline(mse, **mse_kwargs)
        plt.annotate(
            "MSE = {}".format(
                np.array2string(np.asarray(mse), precision=num_label_precision)
            ),
            xy=(mse, 0.8),
            xycoords=('data', 'figure fraction'),
            textcoords='offset points', xytext=(5, 0),
            ha='left', va='bottom', color='k'
        )

    ax.grid(ls='--')

def _zaric_wrap_custom(source_text, separator_chars, width=70, keep_separators=True):
    current_length = 0
    latest_separator = -1
    current_chunk_start = 0
    output = ""
    char_index = 0
    while char_index < len(source_text):
        if source_text[char_index] in separator_chars:
            latest_separator = char_index
        output += source_text[char_index]
        current_length += 1
        if current_length == width:
            if latest_separator >= current_chunk_start:
                # Valid earlier separator, cut there
                cutting_length = char_index - latest_separator
                if not keep_separators:
                    cutting_length += 1
                if cutting_length:
                    output = output[:-cutting_length]
                output += "\n"
                current_chunk_start = latest_separator + 1
                char_index = current_chunk_start
            else:
                # No separator found, hard cut
                output += "\n"
                current_chunk_start = char_index + 1
                latest_separator = current_chunk_start - 1
                char_index += 1
            current_length = 0
        else:
            char_index += 1
    return output

def _zaric_heatmap(y, x, color=None, cmap=None, palette='coolwarm', size=None,
            x_order=None, y_order=None, circular=None,
            ax=None, face_color=None, wrap_x=12, wrap_y=13, square=True,
            cbar=True, cax=None, cbar_kws=None, mask=None,
            color_norm=None, size_norm=None, annot=False, annot_kws=None,
            fmt=".2g", scale_color_norm=True):
    if ax is None:
        ax = plt.gca()

    if color_norm is None:
        color_norm = PowerNorm(0.925)
    
    if scale_color_norm and not color_norm.scaled():
        vmax = max(np.abs(np.nanmin(color)), np.abs(np.nanmax(color)))
        vmin = -vmax
        color_norm.autoscale([vmin, vmax])

    if size is None:
        size = np.ones(len(x))

    if size_norm is None:
        size_norm = PowerNorm(0.5)
    elif isinstance(size_norm, numbers.Number):
        size_norm = PowerNorm(size_norm)
    size_norm.autoscale_None(size)

    if cbar_kws is None:
        cbar_kws = {}
    
    if square:
        ax.set_aspect('equal')

    if face_color is None:
        face_color = '#fdfdfd'

    if color is None:
        color = [1]*len(x)

    if circular is None:
        circular = [False]*len(x)

    if cmap is None:
        cmap = sns.color_palette(palette, as_cmap=True)
    
    def do_wrapping(label, length):
        return _zaric_wrap_custom(label, ["_", "-"], length)
    
    if x_order is None:
        x_names = [t for t in reversed(sorted(set([v for v in x])))]
    else:
        x_names = [t for t in x_order]
        
    # Wrap to help avoid overflow
    x_names = [do_wrapping(label, wrap_x) for label in x_names]

    x_to_num = {p[1]:p[0] for p in enumerate(x_names)}

    if y_order is None:
        y_names = [t for t in sorted(set([v for v in y]))]
    else:
        y_names = [t for t in y_order[::-1]]
        
    # Wrap to help avoid overflow
    y_names = [do_wrapping(label, wrap_y) for label in y_names]

    y_to_num = {p[1]:p[0] for p in enumerate(y_names)}

    ax.tick_params(labelbottom='on', labeltop='on')
    ax.set_xticks([v for k,v in x_to_num.items()])
    ax.set_xticklabels([k for k in x_to_num], rotation=90,
        horizontalalignment='center', linespacing=0.8)
    ax.set_yticks([v for k,v in y_to_num.items()])
    ax.set_yticklabels([k for k in y_to_num], linespacing=0.8)

    ax.grid(False, 'major')
    ax.grid(True, 'minor')
    ax.set_xticks([t + 0.5 for t in ax.get_xticks()], minor=True)
    ax.set_yticks([t + 0.5 for t in ax.get_yticks()], minor=True)

    ax.set_xlim([-0.5, max([v for v in x_to_num.values()]) + 0.5])
    ax.set_ylim([-0.5, max([v for v in y_to_num.values()]) + 0.5])
    ax.set_facecolor(face_color)
    delta_in_pix = ax.transData.transform((1, 1)) - ax.transData.transform((0, 0))

    index = 0
    patch_col = []
    patch_col_ind = []

    if annot_kws is None:
        annot_kws = {}
    else:
        annot_kws = annot_kws.copy()
        
    annot_kws.setdefault("fontsize", 11)
    annot_kws.setdefault("color", "black")

    for cur_x, cur_y, use_circ in zip(x, y, circular):
        if (size[index] == 0 or
            np.isnan(color[index]) or
            (not mask is None and mask[index])
        ):
            index = index + 1
            continue

        wrapped_x_name = do_wrapping(cur_x, wrap_x)
        wrapped_y_name = do_wrapping(cur_y, wrap_y)
        before_coordinate = np.array(
            ax.transData.transform((x_to_num[wrapped_x_name]-0.5,
                                    y_to_num[wrapped_y_name]-0.5)))
        after_coordinate = np.array(
            ax.transData.transform((x_to_num[wrapped_x_name]+0.5,
                                    y_to_num[wrapped_y_name]+0.5)))
        before_pixels = np.round(before_coordinate, 0)
        after_pixels = np.round(after_coordinate, 0)
        desired_fraction = size_norm(size[index])

        delta_in_pix = after_pixels - before_pixels
        gap = np.round((1.0 - desired_fraction) * delta_in_pix / 2, 0)
        # make sure that non-zero sized markers don't disappear
        gap[np.where(delta_in_pix - gap*2 < 3)] -= 3

        start = before_pixels + gap
        ending = after_pixels - gap
        start[0] = start[0] + 1
        ending[1] = ending[1] - 1
        start_doc = ax.transData.inverted().transform(start)
        ending_doc = ax.transData.inverted().transform(ending)
        cur_size = ending_doc - start_doc

        if use_circ:
            cur_rect = patches.Circle(
                (start_doc[0] + cur_size[0] / 2,
                 start_doc[1] + cur_size[1] / 2),
                cur_size[1] / 2, antialiased=True)
        else:
            if square:
                cur_size = (cur_size[0] + cur_size[1]) / 2
                cur_size = (cur_size, cur_size)
            cur_rect = patches.Rectangle(
                (start_doc[0], start_doc[1]),
                cur_size[0], cur_size[1], antialiased=True)

        if annot:
            # annotate the cell with the numeric value
            ax.text(start_doc[0] + cur_size[0] / 2,
                    start_doc[1] + cur_size[1] / 2,
                    ("{:" + fmt + "}").format(color[index]),
                    va='center', ha='center',
                    **annot_kws)
                    
        cur_rect.set_antialiased(True)
        patch_col.append(cur_rect)
        patch_col_ind.append(index)

        index = index + 1

    patch_col = PatchCollection(
        patch_col, array=color[patch_col_ind],
        norm=color_norm, cmap=cmap
    )
    ax.add_collection(patch_col)

    if cbar:
        plt.colorbar(patch_col, cax=cax, **cbar_kws)

def heatmap(df, corr_types=None, map_type='zaric', ax=None, face_color=None,
            annot=None, cbar=True, cbar_kws=None, mask=None,
            row_cluster=False, row_cluster_metric='euclidean',
            row_cluster_method='average', row_cluster_linkage=None,
            col_cluster=False, col_cluster_metric='euclidean',
            col_cluster_method='average', col_cluster_linkage=None,
            **kwargs):
    """
    Plots a heatmap.

    Arguments:
        df: The dataframe to plot.
        corr_types: Optionally specify correlation type using a dataframe of
            CorrType enums for each entry (can be obtained from the corr
            function). When specified, numeric correlations are plotted using
            different markers.
        map_type: One of 'zaric', 'standard', 'dendrograms':
            * 'zaric' (default): a special heatmap, where magnitude is
                indicated by size of the elements as well as their colour.
            * 'standard': a standard heatmap plotted using sns.heatmap;
            * 'dendrograms': a heatmap with dendrograms, using sns.clustermap.
        ax: The matplotlib axis to use for the plotting (not supported for 
            map_type 'dendrograms').
        annot: Whether to also annotate the squares with numbers (defaults to
            True for map_type 'standard' and 'dendrograms'; and to 'False' for
            'zaric').
        cbar: Whether to include a colorbar.
        cbar_kws: Additional kwargs to use when plotting the colorbar.
        mask: An array or a dataframe that indicates whether a value should
            be masked out (True) or displayed (False).
        row_cluster: Whether to use hierarchical clustering to reorder the rows.
        row_cluster_metric: The metric to use for clustering the rows 
            (see _DendrogramPlotter in seaborn.matrix).
        row_cluster_method: The method to use for clustering the rows
            (see _DendrogramPlotter in seaborn.matrix).
        row_cluster_linkage: The linkage to use for clustering the rows
            (see _DendrogramPlotter in seaborn.matrix).
        col_cluster: Whether to use hierarchical clustering to reorder the cols.
        col_cluster_metric: The metric to use for clustering the columns 
            (see _DendrogramPlotter in seaborn.matrix).
        col_cluster_method: The method to use for clustering the columns
            (see _DendrogramPlotter in seaborn.matrix).
        col_cluster_linkage: The linkage to use for clustering the columns
            (see _DendrogramPlotter in seaborn.matrix).
        square: Whether equal aspect ratio should be used for the axes or not
            (defaults to True).
        **kwargs: Any remaining kwargs are passed to the plotting function.
    """
    if map_type == 'dendrograms':
        if not ax is None:
            raise ValueError("Argument 'ax' is not supported for map_type == 'dendrograms'.")
    else:
        if ax is None:
            ax = plt.gca()

    if not mask is None:
        mask = np.asarray(mask)

    if not corr_types is None:
        corr_types = np.asarray(corr_types)

    if row_cluster and not map_type == 'dendrograms':
        row_ind = _DendrogramPlotter(
            df, axis=0, metric=row_cluster_metric,
            method=row_cluster_method, linkage=row_cluster_linkage,
            label=False, rotate=False
        ).reordered_ind

        df = df.reindex(df.index[row_ind])

        if not mask is None:
            mask = mask[row_ind, :]
        
        if not corr_types is None:
            corr_types = corr_types[row_ind, :]

    if col_cluster and not map_type == 'dendrograms':
        col_ind = _DendrogramPlotter(
            df, axis=1, metric=col_cluster_metric,
            method=col_cluster_method, linkage=col_cluster_linkage,
            label=False, rotate=False
        ).reordered_ind
        
        df = df.reindex(df.columns[col_ind], axis=1)
        
        if not mask is None:
            mask = mask[:, col_ind]

        if not corr_types is None:
            corr_types = corr_types[:, col_ind]

    if map_type == "zaric":
        if annot is None:
            annot = False

        l = np.asarray(list(itertools.product(df.index, df.columns)))
        x = l[:, 0]
        y = l[:, 1]
        v = df.values.reshape(-1)
        m = mask.reshape(-1) if not mask is None else None
        circ = np.zeros(len(x))
        if not corr_types is None:
            circ[np.where(corr_types.reshape(-1) == CorrType.num_vs_num)] = True

        default_kwargs = dict(
            color=v,
            size=np.abs(v),
            circular=circ
        )
        default_kwargs.update(**kwargs)
        kwargs = default_kwargs

        _zaric_heatmap(
            x, y,
            ax=ax,
            face_color=face_color,
            cbar=cbar,
            cbar_kws=cbar_kws,
            mask=m,
            x_order=df.columns,
            y_order=df.index,
            annot=annot,
            **kwargs
        )

        ax.set_xlabel(df.columns.name)
        ax.set_ylabel(df.index.name)

    elif map_type == 'standard' or map_type == 'dendrograms':
        if annot is None:
            annot = True

        if face_color is None:
            face_color = 'black'

        default_kwargs = dict(center=0, square=True, linewidths=1,
                              annot=annot)
        default_kwargs.update(**kwargs)
        kwargs = default_kwargs

        if map_type == 'dendrograms':
            del kwargs['square']
            sns.clustermap(df, cbar=cbar, cbar_kws=cbar_kws,
                           mask=mask, **kwargs)
        else:
            sns.heatmap(df, ax=ax, cbar=cbar, cbar_kws=cbar_kws,
                        mask=mask, **kwargs)
        
        if ax is None: ax = plt.gcf().axes[2]
        ax.set_facecolor(face_color)
        ax.xaxis.set_tick_params(rotation=45)
        plt.setp(ax.get_xticklabels(),
            rotation_mode="anchor", horizontalalignment="right")
    
    else:
        raise ValueError("Unknown map_type '{}'.".format(map_type))

def _mask_corr_significance(mask, p, p_bound):
    """
    Adds True to the mask wherever p >= p_bound.
    """
    mask = np.asarray(mask)
    mask[np.where(p >= p_bound)] = True

def _mask_diagonal(mask):
    """
    Sets the mask's diagonal to True.
    """
    mask = np.asarray(mask)
    np.fill_diagonal(mask, True)

def corr_heatmap(data_frame, categorical_inputs=None, numeric_inputs=None,
                 corr_method=None, nan_strategy='mask', nan_replace_value=0,
                 sym_u=False, mask_diagonal=True, p_bound=None, ax=None,
                 map_type='zaric', annot=None, face_color=None, square=True,
                 mask=None, **kwargs):
    """
    Plots a correlation matrix using the heatmap function.

    Returns r, p, ct, where r is the correlation matrix, p are its p-values and
        ct are the correlation types (all computed by corr).

    Arguments:
        data_frame: The dataframe to plot correlations for.
        categorical_inputs: Names of the columns that hold categorical inputs;
            see more in the documentation of .corr.corr.
        numeric_inputs: Names of the columns that hold numeric inputs;
            see more in the documentation of .corr.corr.
        corr_method: The correlation method to be passed to corr;
            see more in the documentation of .corr.corr.
        nan_strategy: Specifies how to handle NaNs; see more in the
            documentation of .corr.corr.
        nan_replace_value: The value to replace NaNs with; see more in the
            documentation of .corr.corr.
        sym_u: If True, the symmetric variant of the uncertainty 
            coefficient is used instead of the basic asymmetric variant.
            Defaults to False.
        mask_diagonal: Whether to mask the diagonal of the matrix (defaults
            to true as the diagonal is non-informative).
        p_bound: The p-value bound. If specified, elements with greater
            p-values are masked out.
        ax: The matplotlib axis to use for the plotting (not supported for 
            map_type 'dendrograms').
        map_type:  map_type: One of 'zaric', 'standard', 'dendrograms':
            * 'zaric' (default): a special heatmap, where magnitude is
                indicated by size of the elements as well as their colour.
            * 'standard': a standard heatmap plotted using sns.heatmap;
            * 'dendrograms': a heatmap with dendrograms, using sns.clustermap.
        annot: Whether to also annotate the squares with numers; see more in
            heatmap's docstring.
        face_color: The heatmap's face color.
        square: Whether equal aspect ratio should be used for the axes or not
            (defaults to True).
        mask: An array or a dataframe that indicates whether a value should
            be masked out (True) or displayed (False).
        **kwargs: Any remaining kwargs are passed to the heatmap function.
    """

    r, p, ct = corr(data_frame, categorical_inputs=categorical_inputs,
                 numeric_inputs=numeric_inputs, corr_method=corr_method,
                 nan_strategy=nan_strategy, nan_replace_value=nan_replace_value,
                 sym_u=sym_u, return_corr_types=True)

    mask = np.zeros(r.shape) if mask is None else np.copy(mask)
    
    if not p_bound is None:
        _mask_corr_significance(mask, p, p_bound)

    if mask_diagonal:
        _mask_diagonal(mask)
    
    heatmap(r, corr_types=ct, map_type=map_type, ax=ax, face_color=face_color,
            annot=annot, square=square, mask=mask, **kwargs)

    return r, p, ct

class ColGrid:
    def __init__(self, data, x_cols, y_cols=None, interact="product",
                 col_wrap=None, height=3, aspect=4/3, ):
        """
        Creates a grid of plots to which a plot can be mapped using ColGrid.map.
        
        Arguments:
            data: The dataframe to use for the grid.
            x_cols: The columns that will go on the x axis.
            y_cols: The columns that will go on the y axis.
            interact: The interactions between x_cols and y_cols:
                * 'product': plot each x against each y;
                * 'zip': zip the x_cols and y_cols and iterate through them;
                * 'comb': plot combinations of x_cols (y_cols must be None);
            col_wrap: The number of columns in the grid's layout.
            height: Height of the grid.
            aspect: The grid's aspect ratio.
        """
        if interact == "comb" and not y_cols is None:
            raise ValueError("When using interact == 'comb', y_cols must be None.")

        self.data = data
        self.x_cols = x_cols if not isinstance(x_cols, str) else [x_cols]
        self.y_cols = y_cols if not (isinstance(y_cols, str) or y_cols is None) else [y_cols]
        self.interact = interact

        if col_wrap is None:
            col_wrap = min(4, len(self.x_cols)*len(self.y_cols))

        self.col_wrap = col_wrap
        self.height = height
        self.aspect = aspect

    def map_dataframe(self, func, *args, **kwargs):
        kwargs = kwargs.copy()
        kwargs['data'] = self.data
        return self.map(func, *args, **kwargs)

    def map(self, func, *args, **kwargs):
        height = self.height
        width = self.height * self.aspect
        
        if self.interact == "product":
            xycol_iter = itertools.product(self.x_cols, self.y_cols)
            num_plots = len(self.x_cols) * len(self.y_cols)
        elif self.interact == "zip":
            xycol_iter = zip(self.x_cols, self.y_cols)
            num_plots = min(len(self.x_cols), len(self.y_cols))
        elif self.interact == "comb":
            xycol_iter = itertools.combinations(self.x_cols, 2)
            n = len(self.x_cols); k = 2
            num_plots = math.factorial(n) / (math.factorial(k) * math.factorial(n - k))
        else:
            raise ValueError("Uknown interact method '{}'.".format(self.interact))

        num_rows = int(np.ceil(num_plots / self.col_wrap))
        fig, axes = plt.subplots(num_rows, self.col_wrap, squeeze=False)
        axes = np.ravel(axes)
        xycol_iter = zip(xycol_iter, axes)

        for iax, ((x_col, y_col), ax) in enumerate(xycol_iter):
            plt.sca(ax)

            if y_col is None:
                func(x=x_col, *args, **kwargs)
            else:
                func(x=x_col, y=y_col, *args, **kwargs)
            
            ax.set_xlabel(x_col)
            if not y_col is None:
                ax.set_ylabel(y_col)

        for ax in axes[iax+1:]:
            ax.axis('off')

        fig.set_size_inches(self.col_wrap * width, num_rows * height)
        plt.tight_layout()

        return fig, axes

def infer_orient(x, y, orient=None):
    """Determine how the plot should be oriented based on the data."""
    orient = str(orient)

    def is_categorical(s):
        return pd.api.types.is_categorical_dtype(s)

    def is_not_numeric(s):
        try:
            np.asarray(s, dtype=np.float)
        except ValueError:
            return True
        return False

    no_numeric = "Neither the `x` nor `y` variable appears to be numeric."

    if orient.startswith("v"):
        return "v"
    elif orient.startswith("h"):
        return "h"
    elif x is None:
        return "v"
    elif y is None:
        return "h"
    elif is_categorical(y):
        if is_categorical(x):
            raise ValueError(no_numeric)
        else:
            return "h"
    elif is_not_numeric(y):
        if is_not_numeric(x):
            raise ValueError(no_numeric)
        else:
            return "h"
    else:
        return "v"

def sorted_order(func, by='median'):
    """
    Orders the elements in a boxplot or a violinplot.

    Arguments:
        by: What to order the elements by; 'median' is used by default.
    """
    def wrapper(x=None, y=None, data=None, orient=None, **kwargs):
        if not data is None:
            xx = data[x]
            yy = data[y]
        else:
            xx = x
            yy = y
        
        df = pd.concat([pd.Series(xx), pd.Series(yy)], axis=1)
        
        orient = infer_orient(xx, yy, orient)

        if orient == 'h':
            groupby_col = df.columns[1]
            other_col = df.columns[0]
        else:
            groupby_col = df.columns[0]
            other_col = df.columns[1]
        
        df_groups = df.groupby(groupby_col)[other_col]
        sort_method = getattr(df_groups, by)
        df_med = sort_method()
        order = df_med.sort_values().index.tolist()
                    
        return func(x=x, y=y, data=df, order=order, orient=orient, **kwargs)
    
    return wrapper
             
def crosstab_plot(
    x, y, data=None, dropna=False, shownan=False,
    normalize=None, **kwargs
):
    """
    Plots a crosstabulation of the different unique values from x and y,
    displaying the counts of their co-occurences.

    Arguments:
        x: A column name (if data not None) or a Series object
            (e.g. a dataframe column).
        y: A column name (if data not None) or a Series object
            (e.g. a dataframe column).
        dropna: Whether to drop entries where at least one of x and y
            is missing a value.
        shownan: Whether to include NaN entries in the crosstabulation
            or drop them before the dataframe is returned.
        normalize: Whether to normalize the crosstabulation. Can be
            'rows', 'columns' or None (default; no normalization applied).
        **kwargs: Any remaining kwargs are passed to the heatmap function.
    """
    if not data is None:
        x = data[x]
        y = data[y]
    tab = numpy_crosstab(y, x, dropna=dropna,
        shownan=shownan, normalize=normalize)
    heatmap(tab, **kwargs)
    return tab

def _groupby_propplot(x, y, data=None):
    if not data is None:
        x = data[x]
        y = data[y]
    df = pd.concat([x, y], axis=1)
    propby = df.groupby(x.name)[y.name].mean()
    sns.barplot(x=propby.index, y=propby)

def proportion_plot(df, x_col, prop_cols):
    """
    Groups the dataframe by each of the prop_cols and plots the proportions
    of x_col's values across each grouping using several bar plots.

    Arguments:
        df: The dataframe to plot.
        x_col: Name of the categorical column to show proportions for.
        prop_cols: A string or a list of strings specifying the column name(s)
            of the columns to group by.
    """
    scalar = False
    
    if isinstance(prop_cols, str):
        prop_cols = [prop_cols]
        scalar = True
    
    figs = []
    
    for prop_col in prop_cols:        
        dumm = pd.get_dummies(df[prop_col])
        dumm = dumm.rename(columns=lambda x: "{}={}".format(prop_col, x))
        
        dumm_df = pd.concat([df[x_col], dumm], axis=1)
        g = ColGrid(dumm_df, "Sex", dumm.columns)
        figs.append(g.map(_groupby_propplot))
        
    if scalar:
        return figs[0]
    else:
        return figs

def imscatter(x, y, images, ax=None, zoom=1,
              frame_cmap=None, frame_c=None,
              frame_linewidth=1, **kwargs):
    """
    Creates a scatter plot, where images are plotted instead of points.

    Arguments:
        x: The horizontal positions of all the points.
        y: The vertical positions of all the points.
        images: An image for each of the points.
        ax: The matplotlib axis to use for the plotting (not supported for 
            map_type 'dendrograms').
        zoom: The zoom of the OffsetImages when they are added to the plot.
        frame_cmap: The colormap to use for the images' frames.
        frame_c: The color(s) to use for the images' frames.
        frame_linewidth: The linewidth of the images' frames.
        **kwargs: Any remaining kwargs are passed to the OffsetImage function.
    """
    if ax is None:
        ax = plt.gca()
        
    if isinstance(frame_cmap, str):
        frame_cmap = plt.cm.get_cmap(frame_cmap)
    elif frame_cmap is None:
        frame_cmap = plt.cm.get_cmap('jet')
    
    if len(images) == 1:
        images = [images[0] for i in range(len(x))]
        
    if frame_c is None:
        frame_c = ['k' for i in range(len(x))]

    x, y = np.atleast_1d(x, y)
    artists = []
    
    for i, (x0, y0) in enumerate(zip(x, y)):
        fc = frame_c[i]
        if isinstance(fc, numbers.Number):
            fc = frame_cmap(fc)
      
        im = OffsetImage(images[i], zoom=zoom, **kwargs)
        ab = AnnotationBbox(im, (x0, y0), xycoords='data', frameon=True,
                            bboxprops=dict(edgecolor=fc,
                                           linewidth=frame_linewidth))
        artists.append(ax.add_artist(ab))
        
    ax.update_datalim(np.column_stack([x, y]))
    ax.autoscale()
    
    return artists

def smoothscatter(
    x: Optional[Union[str, np.ndarray, pd.Series]] = None,
    y: Optional[Union[str, np.ndarray, pd.Series]] = None,
    data: Optional[Union[pd.DataFrame, pd.Series]] = None,
    smoother: Optional[_BaseSmoother] = None,
    scatter: bool = True,
    smoothed: bool = True,
    linreg: bool = False,
    ci: Optional[int] = 95,
    ci_linreg: Optional[int] = None,
    dropna: bool =True,
    x_jitter: Optional[float] = None,
    y_jitter: Optional[float] = None,
    label: Optional[str] = None,
    label_smoothed: Optional[str] = None,
    label_linreg: Optional[str] = None,
    color=None,
    alpha: float = 0.8,
    marker='o',
    scatter_kws: Optional[dict] = None,
    smoothed_kws: Optional[dict] = None,
    linreg_kws: Optional[dict] = None,
    ci_kws: Optional[dict] = None,
    ax=None,
    linewidth: float = 2,
    smooth_fraction: float = 0.5,
    smooth_iterations: float = 1,
    interval_type: str = 'confidence_interval',
):
    """
    Plots a scatter plot of x and y, with an optional smoothed line.

    Arguments:
        x (Union[str, np.ndarray, pd.Series], optional): The horizontal
            positions of the points. If a string is passed, it is
            interpreted as the name of a column in the data dataframe. If None
            is passed, the index of the dataframe is used.
        y (Union[str, np.ndarray, pd.Series], optional): The vertical
            positions of the points. If a string is passed, it is interpreted
            as the name of a column in the dataframe. If None is passed, the
            data dataframe is expected to be a pd.Series or to have a single
            column, which is used as y.
        data (Union[pd.DataFrame, pd.Series], optional): A dataframe to use
            for x and y. If x and y are not passed, this dataframe is used
            for both.
        smoother (tsmoothie.smoother._BaseSmoother, optional): A tsmoothie
            smoother to use for the smoothed line.
        scatter (bool): Whether to plot the scatter plot.
        smoothed (bool): Whether to plot the smoothed line.
        linreg (bool): Whether to also plot a linear regression line.
        ci (int, optional): The confidence interval to use for the smoothed
            line. If None, no confidence interval is plotted.
        ci_linreg (int, optional): The confidence interval used for the
            linear regression. If None (default), no confidence interval is
            plotted.
        dropna (bool): Whether to drop entries where at least one of x and y
            is missing a value.
        x_jitter (float, optional): The amount of jitter to apply to the x
            values. If None, no jitter is applied.
        y_jitter (float, optional): The amount of jitter to apply to the y
            values. If None, no jitter is applied.
        label (str, optional): The label to use for the plot. If a scatter plot
            is plotted, then the label is used for it. If not, it is used for
            the smoothed line.
        label_smoothed: The label to use for the smoothed line. (Overrides
            label if both are passed, even when the scatter plot is off.)
        label_linreg: The label to use for the linear regression line.
        color: The color to use for the plots.
        alpha: The alpha to use for the scatter plot.
        marker: The marker to use for the scatter plot.
        scatter_kws (dict, optional): Any kwargs to pass to the scatter plot.
            Arguments specified in this dict override the other arguments.
        smoothed_kws (dict, optional): Any kwargs to pass to the smoothed line.
            Arguments specified in this dict override the other arguments.
        linreg_kws (dict, optional): Any kwargs to pass to the linear
            regression line plot (created using seaborn's regplot).
        ci_kws (dict, optional): Any kwargs to pass to the confidence interval
            plot.
        ax: The matplotlib axis to use for the plotting.
        linewidth (float): The linewidth of the smoothed line.
        smooth_fraction (float): The fraction of the data to use for the
            smoothed line. This is only used if smoother is None, i.e. if a
            default Lowess smoother is constructed.
        smooth_iterations (float): The number of iterations to use for the
            smoothed line. This is only used if smoother is None, i.e. if a
            default Lowess smoother is constructed.
        interval_type (str): The type of interval to use for the smoothed line.
            The supported options depend on the smoother. For the default
            Lowess smoother, the supported options are 'confidence_interval',
            'prediction_interval' and 'sigma_interval'.
    
    Returns:
        The matplotlib axis used for the plotting.
    """
    if ax is None:
        ax = plt.gca()

    if color is None:
        lines, = ax.plot([], [])
        color = lines.get_color()
        lines.remove()

    color = mpl.colors.rgb2hex(mpl.colors.colorConverter.to_rgb(color))

    if (
        ((x is None) or isinstance(x, str)) or
        ((y is None) or isinstance(y, str))
     ) and data is None:
        raise ValueError("The function needs some data to plot")

    if scatter_kws is None:
        scatter_kws = {}

    if smoothed_kws is None:
        smoothed_kws = {}

    if linreg_kws is None:
        linreg_kws = {}
    else:
        linreg_kws = linreg_kws.copy()

    if ci_kws is None:
        ci_kws = {}
    else:
        ci_kws = ci_kws.copy()
    
    linreg_kws.setdefault('scatter', False)
    linreg_kws.setdefault('color', 'k')
    linreg_kws.setdefault('ci', ci_linreg)
    linreg_kws.setdefault('label', label_linreg)
    
    line_kws = linreg_kws.pop('line_kws', {}).copy()
    line_kws.setdefault('linewidth', 2)
    linreg_kws['line_kws'] = line_kws

    if x is None:
        x = data.index

    if y is None:
        if isinstance(data, pd.Series):
            y = data.values
        elif data.shape[1] == 1:
            y = data.iloc[:, 0]
        else:
            raise ValueError("When y is None, the data dataframe is expected to have a single column.")

    if isinstance(x, str):
        x = data[x]
    elif isinstance(x, pd.Series):
        x = x.values

    if isinstance(y, str):
        y = data[y]
    elif isinstance(y, pd.Series):
        y = y.values

    if dropna:
        not_na = pd.notna(x) & pd.notna(y)
        x = x[not_na]
        y = y[not_na]

    sort_index = x.argsort()
    y_sort = y[sort_index]

    if smoother is None:
        smoother = LowessSmoother(
            smooth_fraction=smooth_fraction,
            iterations=smooth_iterations
        )

    smoother.smooth(y_sort)

    if not ci is None:
        low, up = smoother.get_intervals(interval_type, confidence = 1-ci/100)

    if scatter:
        if x_jitter is not None:
            x_jit = x + np.random.normal(0, x_jitter, len(x))
        else:
            x_jit = x

        if y_jitter is not None:
            y_jit = y + np.random.normal(0, y_jitter, len(y))
        else:
            y_jit = y

        scatter_color = scatter_kws.pop('color', color)
        scatter_alpha = scatter_kws.pop('alpha', alpha)

        ax.scatter(
            x_jit, y_jit, label=label, color=scatter_color, marker=marker,
            alpha=scatter_alpha, **scatter_kws
        )

        label = None

    if smoothed:
        smoothed_color = smoothed_kws.pop('color', color)
        linewidth = smoothed_kws.pop('linewidth', linewidth)
        if label_smoothed is None: label_smoothed = label
        label_smoothed = smoothed_kws.pop('label', label_smoothed)
       
        ax.plot(
            x[sort_index], smoother.smooth_data[0], color=smoothed_color,
            linewidth=linewidth, label=label_smoothed, **smoothed_kws
        )
        
        if not ci is None:
            ci_kws.setdefault('color', smoothed_color)
            ci_kws.setdefault('alpha', 0.3)
            ax.fill_between(x[sort_index], low[0], up[0], **ci_kws)

    if linreg:
        sns.regplot(x=x, y=y, ax=ax, **linreg_kws)

    return ax
