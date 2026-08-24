from typing import Optional, Union, Dict, Hashable


class PromptTemplate:
    def __init__(self,
                 template: Union[Dict, str],  # 提示模板，可以是字典或字符串
                 column_token_map: Dict,     # 列名与标记的映射字典
                 selected_column_name: Optional[str] = None,  # 可选的选定列名
                 ice_token: Optional[str] = None,  # 可选的ICE标记
                 ) -> None:
        """
        初始化PromptTemplate类
        参数:
            template: 提示模板，可以是字典或字符串
            column_token_map: 列名与标记的映射字典
            selected_column_name: 可选的选定列名，用于选择特定的模板
            ice_token: 可选的ICE标记，用于在模板中占位
        """
        self.template = template
        self.column_token_map = column_token_map
        self.selected_column_name = selected_column_name
        self.ice_token = ice_token

    def generate_item(self, entry: Dict, output_field: Optional[Hashable] = None,
                      output_field_replace_token: Optional[str] = '',
                      ice_field_replace_token: Optional[str] = '') -> str:

        if isinstance(self.template, str):
            tp = self.template
        else:
            pred_label = None
            if self.selected_column_name is not None:
                pred_label = entry[self.selected_column_name]
            if pred_label in self.template.keys():
                tp = self.template[pred_label]
            else:
                tp = self.template[list(self.template.keys())[0]]

        if self.ice_token is not None:
            tp = tp.replace(self.ice_token, ice_field_replace_token)

        for key, token in self.column_token_map.items():
            if output_field is not None and key == output_field:
                tp = tp.replace(token, output_field_replace_token)
            else:
                tp = tp.replace(token, str(entry[key]))
        return tp