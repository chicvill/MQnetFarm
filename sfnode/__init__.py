class Node:
    """스마트팜의 개별 장치(센서, 액추에이터 등)를 나타내는 클래스"""
    def __init__(self, node_id, name, node_type):
        self.node_id = node_id
        self.name = name
        self.node_type = node_type
        self.status = "offline"
        self.value = 0

    def __repr__(self):
        return f"<Node ID: {self.node_id}, Name: {self.name}, Type: {self.node_type}, Status: {self.status}>"


class NodeManager:
    """노드의 생성, 수정, 삭제, 조회를 관리하는 클래스"""
    def __init__(self):
        self.nodes = {}

    def add_node(self, node_id, name, node_type):
        """노드 추가 (생성)"""
        if node_id in self.nodes:
            print(f"오류: ID '{node_id}'는 이미 존재합니다.")
            return False
        new_node = Node(node_id, name, node_type)
        self.nodes[node_id] = new_node
        print(f"성공: 노드 '{name}'(ID: {node_id})가 추가되었습니다.")
        return new_node

    def update_node(self, node_id, **kwargs):
        """노드 정보 수정"""
        if node_id not in self.nodes:
            print(f"오류: ID '{node_id}'를 찾을 수 없습니다.")
            return False
        
        node = self.nodes[node_id]
        for key, value in kwargs.items():
            if hasattr(node, key):
                setattr(node, key, value)
                print(f"수정: {node_id}의 {key}가 '{value}'로 변경되었습니다.")
        return True

    def delete_node(self, node_id):
        """노드 삭제"""
        if node_id in self.nodes:
            del_name = self.nodes[node_id].name
            del self.nodes[node_id]
            print(f"삭제: 노드 '{del_name}'(ID: {node_id})가 삭제되었습니다.")
            return True
        print(f"오류: ID '{node_id}'를 찾을 수 없습니다.")
        return False

    def list_nodes(self):
        """모든 노드 목록 출력"""
        print("\n--- 현재 노드 목록 ---")
        for node in self.nodes.values():
            print(node)
        print("---------------------\n")
