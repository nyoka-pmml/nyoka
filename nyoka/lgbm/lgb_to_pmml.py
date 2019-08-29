from __future__ import absolute_import

import sys, os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(BASE_DIR)
import numpy as np
import PMML44 as pml
import nyoka.skl.skl_to_pmml as sklToPmml
import nyoka.xgboost.xgboost_to_pmml as xgboostToPmml
import json
from skl import pre_process as pp
from datetime import datetime



def lgb_to_pmml(pipeline, col_names, target_name, pmml_f_name='from_lgbm.pmml'):
    """
    Exports LGBM pipeline object into pmml

    Parameters
    ----------
    pipeline :
        Contains an instance of Pipeline with preprocessing and final estimator
    col_names : List
        Contains list of feature/column names.
    target_name : String
        Name of the target column.
    pmml_f_name : String
        Name of the pmml file. (Default='from_lgbm.pmml')

    Returns
    -------
    Exports the generated PMML object to `pmml_f_name`

    """
    try:
        model = pipeline.steps[-1][1]
    except:
        raise TypeError("Exporter expects pipeleine_instance and not an estimator_instance")
    else:
        if isinstance(col_names, np.ndarray):
            col_names = col_names.tolist()
        ppln_sans_predictor = pipeline.steps[:-1]
        trfm_dict_kwargs = dict()
        derived_col_names = col_names
        categoric_values = tuple()
        mining_imp_val = tuple()
        if ppln_sans_predictor:
            pml_pp = pp.get_preprocess_val(ppln_sans_predictor, col_names, model)
            trfm_dict_kwargs['TransformationDictionary'] = pml_pp['trfm_dict']
            derived_col_names = pml_pp['derived_col_names']
            col_names = pml_pp['preprocessed_col_names']
            categoric_values = pml_pp['categorical_feat_values']
            mining_imp_val = pml_pp['mining_imp_values']
        PMML_kwargs = get_PMML_kwargs(model,
                                      derived_col_names,
                                      col_names,
                                      target_name,
                                      mining_imp_val,
                                      categoric_values)
        pmml = pml.PMML(
            version=sklToPmml.get_version(),
            Header=sklToPmml.get_header(),
            MiningBuildTask=sklToPmml.get_mining_buildtask(pipeline),
            DataDictionary=sklToPmml.get_data_dictionary(model, col_names, target_name, categoric_values),
            **trfm_dict_kwargs,
            **PMML_kwargs
        )
        pmml.export(outfile=open(pmml_f_name, "w"), level=0)
        

def get_PMML_kwargs(model, derived_col_names, col_names, target_name, mining_imp_val,categoric_values):
    """
     It returns all the pmml elements.

    Parameters
    ----------
    model :
        Contains LGB model object.
    derived_col_names : List
        Contains column names after preprocessing
    col_names : List
        Contains list of feature/column names.
    target_name : String
        Name of the target column .
    mining_imp_val : tuple
        Contains the mining_attributes,mining_strategy, mining_impute_value
    categoric_values : tuple
        Contains Categorical attribute names and its values

    Returns
    -------
    algo_kwargs : Dictionary
        Get the PMML model argument based on LGB model object
    """
    algo_kwargs = {'MiningModel': get_ensemble_models(model,
                                                      derived_col_names,
                                                      col_names,
                                                      target_name,
                                                      mining_imp_val,
                                                      categoric_values)}
    return algo_kwargs

def get_ensemble_models(model, derived_col_names, col_names, target_name, mining_imp_val,categoric_values):
    """
    It returns the Mining Model element of the model

    Parameters
    ----------
    model :
        Contains LGB model object.
    derived_col_names : List
        Contains column names after preprocessing.
    col_names : List
        Contains list of feature/column names.
    target_name : String
        Name of the Target column.
    mining_imp_val : tuple
        Contains the mining_attributes,mining_strategy, mining_impute_value.
    categoric_values : tuple
        Contains Categorical attribute names and its values

    Returns
    -------
    Returns the MiningModel for the given LGB model
    """
    model_kwargs = sklToPmml.get_model_kwargs(model, col_names, target_name, mining_imp_val,categoric_values)
    mining_models = list()
    mining_models.append(pml.MiningModel(
        modelName="LightGBModel",
        Segmentation=get_outer_segmentation(model, derived_col_names, col_names, target_name, mining_imp_val,categoric_values),
        **model_kwargs
    ))
    return mining_models



def get_outer_segmentation(model, derived_col_names, col_names, target_name, mining_imp_val,categoric_values):
    """
    It returns the Segmentation element of the model.

    Parameters
    ----------
    model :
        Contains LGB model object.
    derived_col_names : List
        Contains column names after preprocessing.
    col_names : List
        Contains list of feature/column names.
    target_name : String
        Name of the Target column.
    mining_imp_val : tuple
        Contains the mining_attributes,mining_strategy, mining_impute_value
    categoric_values : tuple
        Contains Categorical attribute names and its values

    Returns
    -------
    segmentation :
        Get the outer most Segmentation of an LGB model

    """

    if 'LGBMRegressor' in str(model.__class__):
        segmentation=get_segments(model, derived_col_names, col_names, target_name, mining_imp_val,categoric_values)
    else:
        segmentation = pml.Segmentation(
            multipleModelMethod=get_multiple_model_method(model),
            Segment=get_segments(model, derived_col_names, col_names, target_name, mining_imp_val,categoric_values)
        )
    return segmentation

def get_segments(model, derived_col_names, col_names, target_name, mining_imp_val,categoric_values):
    """
    It returns the Segment element of the model.

   Parameters
   ----------
   model :
       Contains LGB model object.
   derived_col_names : List
       Contains column names after preprocessing.
   col_names : List
       Contains list of feature/column names.
   target_name : String
       Name of the Target column.
   mining_imp_val : tuple
        Contains the mining_attributes,mining_strategy, mining_impute_value
    categoric_values : tuple
        Contains Categorical attribute names and its values

   Returns
   -------
   segment :
       Get the Segments for the Segmentation element.

   """
    segments = None
    if 'LGBMClassifier' in str(model.__class__):
        segments=get_segments_for_lgbc(model, derived_col_names, col_names, target_name, mining_imp_val,categoric_values)
    elif 'LGBMRegressor' in str(model.__class__):
        segments=get_segments_for_lgbr(model, derived_col_names, col_names, target_name, mining_imp_val,categoric_values)
    return segments

def generate_Segments_Equal_To_Estimators(val, derived_col_names, col_names):
    """
    It returns number of Segments equal to the estimator of the model.

    Parameters
    ----------
    val : List
        Contains nodes in json format.
    derived_col_names : List
        Contains column names after preprocessing.
    col_names : List
        Contains list of feature/column names.
    Returns
    -------
    segments_equal_to_estimators :
         Returns list of segments equal to number of estimator of the model
    """
    segments_equal_to_estimators = []
    for i in range(len(val)):
        main_node = pml.Node(True_=pml.True_())
        mining_field_for_innner_segments = col_names
        m_flds = []
        create_node(val[i], main_node, derived_col_names)
        for name in mining_field_for_innner_segments:
            m_flds.append(pml.MiningField(name=name))

        segments_equal_to_estimators.append((pml.Segment(id=i + 1, True_=pml.True_(),
                                                     TreeModel=pml.TreeModel(functionName="regression",
                                                     modelName="DecisionTreeModel",
                                                                         missingValueStrategy="none",
                                                                         noTrueChildStrategy="returnLastPrediction",
                                                                         splitCharacteristic="multiSplit",
                                                                         Node=main_node,
                                                                         MiningSchema=pml.MiningSchema(
                                                                             MiningField=m_flds)))))

    return segments_equal_to_estimators



def get_segments_for_lgbr(model, derived_col_names, feature_names, target_name, mining_imp_val,categorical_values):
    """
        It returns all the Segments element of the model

       Parameters
       ----------
       model :
           Contains LGB model object.
       derived_col_names : List
           Contains column names after preprocessing.
       feature_names : List
           Contains list of feature/column names.
       target_name : List
           Name of the Target column.
       mining_imp_val : tuple
            Contains the mining_attributes,mining_strategy, mining_impute_value
        categoric_values : tuple
            Contains Categorical attribute names and its values

       Returns
       -------
       segment :
           Get the Segmentation element which contains inner segments.

       """
    segments = list()
    main_key_value = []
    lgb_dump = model.booster_.dump_model()
    for i in range(len(lgb_dump['tree_info'])):
        tree = lgb_dump['tree_info'][i]['tree_structure']
        main_key_value.append(tree)
    segmentation = pml.Segmentation(multipleModelMethod="sum",
                                    Segment=generate_Segments_Equal_To_Estimators(main_key_value, derived_col_names,
                                                                                  feature_names))
    return segmentation


def create_node(obj, main_node,derived_col_names):
    """
    It creates nodes for the internal Decision Trees.

    Parameters
    ----------
    obj : Json
        Contains nodes in json format.
    main_node :
        Contains node build with Nyoka class.
    derived_col_names : List
        Contains column names after preprocessing.
    """

    def create_left_node(obj,derived_col_names):
        nd = pml.Node()
        nd.set_SimplePredicate(
            pml.SimplePredicate(field=xgboostToPmml.replace_name_with_derivedColumnNames(derived_col_names[int(obj['split_feature'])],\
                 derived_col_names), operator='lessOrEqual', value="{:.16f}".format(obj['threshold'])))
        create_node(obj['left_child'], nd, derived_col_names)
        return nd

    def create_right_node(obj,derived_col_names):
        nd = pml.Node()
        nd.set_SimplePredicate(
            pml.SimplePredicate(field=xgboostToPmml.replace_name_with_derivedColumnNames(derived_col_names[int(obj['split_feature'])],\
                 derived_col_names), operator='greaterThan', value="{:.16f}".format(obj['threshold'])))
        create_node(obj['right_child'], nd, derived_col_names)
        return nd

    if 'leaf_index' in obj:
        main_node.set_score(obj['leaf_value'])
    else:

        main_node.add_Node(create_left_node(obj,derived_col_names))
        main_node.add_Node(create_right_node(obj,derived_col_names))


def get_segments_for_lgbc(model, derived_col_names, feature_names, target_name, mining_imp_val,categoric_values):
    """
    It returns all the segments of the LGB classifier.

    Parameters
    ----------
    model :
        Contains LGB model object.
    derived_col_names : List
        Contains column names after preprocessing.
    feature_names: List
        Contains list of feature/column names.
    target_name : String
        Name of the Target column.
    mining_imp_val : tuple
        Contains the mining_attributes,mining_strategy, mining_impute_value
    categoric_values : tuple
        Contains Categorical attribute names and its values

    Returns
    -------
    regrs_models :
        Returns all the segments of the LGB model.
        """
    segments = list()

    if model.n_classes_ == 2:
        main_key_value = []
        lgb_dump = model.booster_.dump_model()
        for i in range(len(lgb_dump['tree_info'])):
            tree = lgb_dump['tree_info'][i]['tree_structure']
            main_key_value.append(tree)
        mining_schema_for_1st_segment = xgboostToPmml.mining_Field_For_First_Segment(feature_names)
        outputField = list()
        outputField.append(pml.OutputField(name="lgbValue", optype="continuous", dataType="double",
                                           feature="predictedValue", isFinalResult="false"))
        out = pml.Output(OutputField=outputField)
        oField=list()
        oField.append("lgbValue")
        segments_equal_to_estimators = generate_Segments_Equal_To_Estimators(main_key_value, derived_col_names,
                                                                             feature_names)
        First_segment = xgboostToPmml.add_segmentation(model,segments_equal_to_estimators, mining_schema_for_1st_segment, out, 1)
        reg_model = sklToPmml.get_regrs_models(model, oField, oField, target_name, mining_imp_val, categoric_values)[0]
        reg_model.normalizationMethod = 'logit'
        last_segment = pml.Segment(True_=pml.True_(), id=2,
                                   RegressionModel=reg_model)
        segments.append(First_segment)

        segments.append(last_segment)
    else:
        main_key_value = []
        lgb_dump = model.booster_.dump_model()
        for i in range(len(lgb_dump['tree_info'])):
            tree = lgb_dump['tree_info'][i]['tree_structure']
            main_key_value.append(tree)
        oField = list()
        for index in range(0, model.n_classes_):
            inner_segment = []
            for in_seg in range(index, len(main_key_value), model.n_classes_):
                inner_segment.append(main_key_value[in_seg])
            mining_schema_for_1st_segment = xgboostToPmml.mining_Field_For_First_Segment(feature_names)
            outputField = list()
            outputField.append(pml.OutputField(name='lgbValue(' + str(index) + ')', optype="continuous",
                                      feature="predictedValue", dataType="float", isFinalResult="true"))
            out = pml.Output(OutputField=outputField)

            oField.append('lgbValue(' + str(index) + ')')
            segments_equal_to_estimators = generate_Segments_Equal_To_Estimators(inner_segment, derived_col_names,
                                                                                 feature_names)
            segments_equal_to_class = xgboostToPmml.add_segmentation(model,segments_equal_to_estimators,
                                                       mining_schema_for_1st_segment, out, index)
            segments.append(segments_equal_to_class)
        reg_model = sklToPmml.get_regrs_models(model,oField,oField,target_name,mining_imp_val,categoric_values)[0]
        reg_model.normalizationMethod = 'softmax'
        last_segment = pml.Segment(True_=pml.True_(), id=model.n_classes_ + 1,
                                   RegressionModel=reg_model)
        segments.append(last_segment)
    return segments

def get_multiple_model_method(model):
    """
    It returns the type of multiple model method for MiningModels.

    Parameters
    ----------
    model :
        Contains LGB model object
    Returns
    -------
    The multiple model method for a MiningModel.

    """
    if 'LGBMClassifier' in str(model.__class__):
        return 'modelChain'
    else:
        return 'sum'

