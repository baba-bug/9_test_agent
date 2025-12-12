import importlib
import json

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "detect_fixations",
            "description": "从头部位置时间序列数据中检测固定点",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "description": "头部位置时间序列数据"
                    },
                    "dt_thresh": {
                        "type": "number",
                        "default": 0.1,
                        "description": "时间间隔阈值"
                    },
                    "dur_thresh": {
                        "type": "number",
                        "default": 0.08,
                        "description": "持续时间阈值"
                    }
                },
                "required": [
                    "data"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_spatial_distribution",
            "description": "分析点集的空间分布特征",
            "parameters": {
                "type": "object",
                "properties": {
                    "points": {
                        "type": "array",
                        "description": "点坐标数组"
                    }
                },
                "required": [
                    "points"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clean_dataframe",
            "description": "对DataFrame进行数据清洗和异常值处理",
            "parameters": {
                "type": "object",
                "properties": {
                    "df": {
                        "type": "object",
                        "description": "输入DataFrame"
                    },
                    "column": {
                        "type": "string",
                        "description": "需要处理的列名"
                    },
                    "threshold": {
                        "type": "number",
                        "default": 0.99,
                        "description": "分位数阈值"
                    }
                },
                "required": [
                    "df",
                    "column"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_group_statistics",
            "description": "分析DataFrame中指定列的分组统计信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "df": {
                        "type": "object",
                        "description": "输入DataFrame"
                    },
                    "column": {
                        "type": "string",
                        "description": "需要分析的数值列名"
                    },
                    "groupby": {
                        "type": "string",
                        "default": "Condition",
                        "description": "分组列名"
                    }
                },
                "required": [
                    "df",
                    "column"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "visualize_distributions",
            "description": "创建数据分布可视化图表",
            "parameters": {
                "type": "object",
                "properties": {
                    "df": {
                        "type": "object",
                        "description": "输入DataFrame"
                    },
                    "column": {
                        "type": "string",
                        "description": "需要可视化的数值列名"
                    },
                    "visualization_type": {
                        "type": "string",
                        "enum": [
                            "condition_boxplot",
                            "correctness_section_boxplot"
                        ],
                        "description": "可视化类型选择"
                    }
                },
                "required": [
                    "df",
                    "column",
                    "visualization_type"
                ]
            }
        }
    }
]

def dispatch_tool(name: str, args: dict) -> str:
    try:
        if name == "detect_fixations":
            module = importlib.import_module("headanalysis")
            func = getattr(module, "detect_fixations")
            # 应用默认参数
            if 'dt_thresh' not in args:
                args['dt_thresh'] = 0.1
            if 'dur_thresh' not in args:
                args['dur_thresh'] = 0.08
            result = func(**args)
            return json.dumps({"fixations": result})
        
        elif name == "analyze_spatial_distribution":
            module = importlib.import_module("headanalysis")
            func = getattr(module, "nearest_neighbor_stats")
            result = func(**args)
            # 假设返回格式为字典，包含mean_distance, std_distance, histogram
            return json.dumps(result)
        
        elif name == "clean_dataframe":
            module = importlib.import_module("headanalysis")
            func = getattr(module, "remove_outliers")
            # 应用默认参数
            if 'threshold' not in args:
                args['threshold'] = 0.99
            result = func(**args)
            # 假设返回格式为元组或字典，包含cleaned_df和removed_count
            if isinstance(result, tuple) and len(result) == 2:
                return json.dumps({"cleaned_df": result[0], "removed_count": result[1]})
            else:
                return json.dumps(result)
        
        elif name == "analyze_group_statistics":
            module = importlib.import_module("headanalysis")
            func = getattr(module, "analyze_condition")
            # 应用默认参数
            if 'groupby' not in args:
                args['groupby'] = "Condition"
            result = func(**args)
            return json.dumps({"statistics": result})
        
        elif name == "visualize_distributions":
            # 根据visualization_type选择具体实现
            vis_type = args.get('visualization_type')
            if vis_type == "condition_boxplot":
                module = importlib.import_module("headanalysis")
                func = getattr(module, "plot_boxplot")
            elif vis_type == "correctness_section_boxplot":
                module = importlib.import_module("headanalysis")
                func = getattr(module, "plot_boxplot_IsCorrect_Section")
            else:
                return json.dumps({"error": f"Unknown visualization_type: {vis_type}"})
            
            # 只传递df和column参数给具体函数
            func_args = {'df': args['df'], 'column': args['column']}
            result = func(**func_args)
            # 假设返回格式为字典，包含plot_data和image_path
            return json.dumps(result)
        
        else:
            return json.dumps({"error": f"Unknown tool name: {name}"})
    
    except Exception as e:
        return json.dumps({"error": str(e)})