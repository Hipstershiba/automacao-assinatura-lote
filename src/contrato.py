class Contrato:
    def __init__(self, titulo, codigo, doc_id, tag, status, ordem_assinatura, data_criacao, data_limite):
        self.titulo = titulo
        self.codigo = codigo
        self.id = doc_id
        self.tag = tag
        self.status = status
        self.ordem_assinatura = ordem_assinatura
        self.data_criacao = data_criacao
        self.data_limite = data_limite
        self.signatarios = []

    def set_signatarios(self, signatarios):
        self.signatarios = [
            {
                'nome': signatario['nome'],
                'cpf': signatario['cpfCnpj'],
                'status': signatario['pivot']['status'],
                'tipo': signatario['pivot']['tipo']
            }
            for signatario in signatarios
        ]

    def identificar_tipo_usuario(self, usuario_cpf):
        for signatario in self.signatarios:
            if usuario_cpf == signatario['cpf']:
                return signatario['tipo']
        return None

    def quem_deve_assinar(self):
        for tipo in self.ordem_assinatura:
            for signatario in self.signatarios:
                if tipo.lower() == signatario['tipo'].lower() and signatario['status'] != 'assinado':
                    return tipo
        return None
    
    def liberar_assinatura(self, usuario_cpf):
        tipo_usuario = self.identificar_tipo_usuario(usuario_cpf)
        if not tipo_usuario:
            return False
        if not self.ordem_assinatura:
            return True
        proximo = self.quem_deve_assinar()
        if not proximo:
            return False
        return tipo_usuario.lower() == proximo.lower()