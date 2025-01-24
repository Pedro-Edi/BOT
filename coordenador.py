
import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import View, button,Select, select

from datetime import datetime,timedelta
import asyncio

from Commands.aluno import duvidas_por_usuario  # Importa o dicionário compartilhado com as dúvidas

class Coordenador(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.atendimento_ativo = False  # Dicionário para controlar atendimentos ativos por usuário

    def obter_duvidas_respondidas(self):
        duvidas_com_respostas = {}
        for usuario_name, duvidas in duvidas_por_usuario.items():
            duvidas_com_resposta = []
            for titulo, dados in duvidas.items():
                if dados.get("respostas"):  # Verifica se há respostas
                    duvidas_com_resposta.append({"titulo": titulo, "dados": dados})
            if duvidas_com_resposta:
                duvidas_com_resposta.sort(key=lambda d: d["dados"]["timestamp_duvida"])
                duvidas_com_respostas[usuario_name] = duvidas_com_resposta
        return duvidas_com_respostas
        
    
    def obter_duvidas_nao_respondidas(self):
        duvidas_agrupadas = {}
        for usuario_name, duvidas in duvidas_por_usuario.items():
            duvidas_sem_resposta = []
            for titulo, dados in duvidas.items():
                if not dados.get("respostas"):  
                    duvidas_sem_resposta.append({"titulo": titulo, "dados": dados})
            if duvidas_sem_resposta:
                duvidas_agrupadas[usuario_name] = duvidas_sem_resposta
        return  duvidas_agrupadas
        
    

    async def gerenciar_timeout(self, interaction, timeout):
        try:
            msg = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user, timeout=timeout)
            return msg
        except asyncio.TimeoutError:
            self.atendimento_ativo = False
            await interaction.followup.send(
                "Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`."
            )
            return None
        
    async def load_demanda_view(self,interaction,usuario_atual):
        demanda_view = DemandaView(self.bot,self,usuario_atual)
        message=await interaction.followup.send(view=demanda_view)
        demanda_view.message=message

    @app_commands.command(description="Visualizar títulos de dúvidas não respondidas e responder.")
    async def proximo_atendimento(self, interaction: discord.Interaction):


        if self.atendimento_ativo:
            await interaction.response.send_message(
                "Você já tem um atendimento em andamento. Por favor, finalize o atendimento atual antes de iniciar outro."
            )
            return

        # Marca o atendimento como ativo
        self.atendimento_ativo = True
        
        await interaction.response.send_message("Bem-vindo!")

        await self.load_demanda_view(interaction,self)


class DemandaView(View):
    def __init__(self, bot,aluno_cog,usuario_atual,timeout=300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog
        self.usuario_atual=usuario_atual
    
    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.message=None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True 
        if self.message:  
            await self.message.edit(content="Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/proximo_atendimento`."
,view=self)
            self.aluno_cog.atendimento_ativo=False
            return

     #FUNÇÃO QUE CARREGA O SUBMENU
    async def load_filtro_duvidas(self,interaction,duvidas_com_respostas,tipo,usuario_atual):
        menu_view = FiltroDuvidas(self.bot, self.aluno_cog,duvidas_com_respostas,tipo,usuario_atual)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message
        
  

    @button(label="Atender próximo", style=discord.ButtonStyle.primary)
    async def atender_próximo(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        
        duvidas_agrupadas=self.aluno_cog.obter_duvidas_nao_respondidas()

        if self.usuario_atual in duvidas_agrupadas:
            usuario_selecionado = self.usuario_atual
        else:
            
            usuarios_com_duvidas_ordenadas = [
                (usuario_name, min(dados["dados"].get("timestamp_duvida", datetime.max) for dados in duvidas))
                for usuario_name, duvidas in duvidas_agrupadas.items()
            ]

            usuarios_com_duvidas_ordenadas.sort(key=lambda x: x[1])

            
            if not usuarios_com_duvidas_ordenadas:
                await interaction.followup.send("Não há dúvidas pendentes no momento.")
                await self.aluno_cog.load_demanda_view(interaction,self.usuario_atual)
                return
            usuario_selecionado = usuarios_com_duvidas_ordenadas[0][0]
            self.usuario_atual = usuario_selecionado
                

            
        duvidas_usuario = duvidas_agrupadas[usuario_selecionado]

        while True:
            lista_titulos = "\n".join([
            f"{i + 1}. {item['titulo']}"
            for i, item in enumerate(duvidas_usuario)
                                                        ])
            await interaction.followup.send(
                f"Dúvidas de {usuario_selecionado}:\n{lista_titulos}\n"
                "Escolha um título pela posição na lista para responder as mensagens."
            )

            escolha_titulo = await self.aluno_cog.gerenciar_timeout(interaction, 300)
        
            if escolha_titulo is None:
                return
            escolha_titulo = escolha_titulo.content.strip()
           
            if not escolha_titulo.isdigit():  # Verifica se não é um número
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue

        
            escolha_titulo_index = int(escolha_titulo) - 1

            if escolha_titulo_index < 0 or escolha_titulo_index >= len(duvidas_usuario):
                await interaction.followup.send("Escolha inválida. Por favor, tente novamente.")
                continue

            titulo_selecionado = duvidas_usuario[escolha_titulo_index]
            titulo = titulo_selecionado["titulo"]
            dados = titulo_selecionado["dados"]
            
            mensagens = dados.get("mensagens", [])
            dados["timestamp_resposta"]=datetime.now()
            
            mensagens_formatadas = "\n".join([f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."

            await interaction.followup.send(
                f"**Título : {titulo}**\n\n"
                f"**Mensagens:**\n{mensagens_formatadas}\n\n"
                "Agora você pode responder a essa dúvida. Envie suas respostas.\n"
                "Envie uma mensagem com somente 'enviar' para encerrar."
            )

            respostas = []
            while True:

                resposta  = await self.aluno_cog.gerenciar_timeout(interaction, 300)
        
                if resposta  is None:
                    return
                resposta = resposta.content.strip()
                

                if resposta.lower() == 'enviar':
                    break
                
                respostas.append(resposta)

            # Adicionar respostas ao título
            dados["respostas"].extend(respostas)
            await interaction.followup.send(
                f"Respostas adicionadas ao título **{titulo}**:\n"
                f"{chr(10).join([f'- {r}' for r in respostas])}\n"
                f"O título foi atualizado com as novas respostas.\n\n"
            )
            await self.aluno_cog.load_demanda_view(interaction,self.usuario_atual)
            print(f'ola,{self.aluno_cog.obter_duvidas_respondidas()}')
            
            return
            

    @button(label="Visualizar respostas", style=discord.ButtonStyle.secondary)
    async def visualizar_respostas(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        duvidas_com_respostas = self.aluno_cog.obter_duvidas_respondidas()
        await self.load_filtro_duvidas(interaction,duvidas_com_respostas,self.usuario_atual,"visualizar")


    @button(label="Editar respostas", style=discord.ButtonStyle.success)
    async def editar_respostas(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        duvidas_com_respostas = self.aluno_cog.obter_duvidas_respondidas()
        await self.load_filtro_duvidas(interaction,duvidas_com_respostas,self.usuario_atual,"editar")


    @button(label="Deletar respostas", style=discord.ButtonStyle.danger)
    async def deletar_resposta(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        duvidas_com_respostas = self.aluno_cog.obter_duvidas_respondidas()
        await self.load_filtro_duvidas(interaction,duvidas_com_respostas,self.usuario_atual,"deletar")
 
                                        
    @button(label="Finalizar demanda", style=discord.ButtonStyle.danger)
    async def finalizar_demanda(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        self.aluno_cog.atendimento_ativo = False
        await interaction.followup.send(
            "Demanda finalizada com sucesso."
        )

class FiltroDuvidas(View):
    def __init__(self, bot, aluno_cog, duvidas,tipo,usuario_atual,timeout=10):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog
        self.duvidas=duvidas
        self.tipo=tipo  
        self.usuario_atual =usuario_atual      

    # FUNÇÃO QUE VERIFICA A INTERAÇÃO DO USUÁRIO COM A VIEW DO MENU
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  
        if self.message:    
            await self.message.edit(content="Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`.",view=self)
            self.aluno_cog.atendimento_ativo=False
            return

    async def disable_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.message = None

    async def show_visualizar_respostas(self, interaction: discord.Interaction,duvidas):

        # Filtra as dúvidas que possuem respostas
        duvidas_com_respostas = duvidas
        print(duvidas_com_respostas)
    

        if not duvidas_com_respostas:
            await interaction.followup.send("Não há respostas registradas para exibir.")
            await self.aluno_cog.load_demanda_view(interaction,self.usuario_atual)
            return
        
      

        # Lista usuários com dúvidas respondidas
        usuarios_com_respostas = sorted(
            duvidas_com_respostas.keys(),
            key=lambda usuario: duvidas_com_respostas[usuario][0]["dados"]["timestamp_duvida"])
            

        while True:
            lista_usuarios = "\n".join([f"{i + 1}. {user}" for i, user in enumerate(usuarios_com_respostas)])
            await interaction.followup.send(
                f"Escolha um usuário para visualizar as respostas associadas às dúvidas:\n{lista_usuarios}"
            )
            escolha_usuario  = await self.aluno_cog.gerenciar_timeout(interaction, 300)
        
            if escolha_usuario is None:
                return
            escolha_usuario = escolha_usuario.content.strip() 
            
            
            if not escolha_usuario.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue
            
        
            escolha_usuario_index = int(escolha_usuario) - 1

            if escolha_usuario_index < 0 or escolha_usuario_index >= len(usuarios_com_respostas):
                await interaction.followup.send("Escolha inválida. Por favor, tente novamente.")
                continue

            usuario_selecionado = usuarios_com_respostas[escolha_usuario_index]
            duvidas_usuario = duvidas_com_respostas[usuario_selecionado]

            while True:
                lista_titulos = "\n".join([f"{i + 1}. {item['titulo']}" for i, item in enumerate(duvidas_usuario)])

            
                await interaction.followup.send(
                    f"Escolha um título para visualizar as respostas:\n{lista_titulos}"
                )

                escolha_titulo  = await self.aluno_cog.gerenciar_timeout(interaction, 300)
        
                if escolha_titulo is None:
                    return
                escolha_titulo = escolha_titulo.content.strip()
                
                
                if not escolha_titulo.isdigit():
                    await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                    continue
            

                escolha_titulo_index = int(escolha_titulo) - 1

                if escolha_titulo_index < 0 or escolha_titulo_index >= len(duvidas_usuario):
                    await interaction.followup.send("Escolha inválida. Por favor, tente novamente.")
                    continue
                
                titulo_selecionado = duvidas_usuario[escolha_titulo_index]
                titulo = titulo_selecionado["titulo"]
                dados = titulo_selecionado["dados"]
                mensagens= dados.get("mensagens", [])
                respostas = dados.get("respostas", [])
                
                mensagens_formatadas = "\n".join(
                [f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."
                respostas_formatadas = "\n".join(
                [f"- {resp}" for resp in respostas]) if respostas else "Nenhuma resposta registrada."

                            
                await interaction.followup.send(
                    f"**Título:** {titulo}\n"
                    f"**Mensagens:**\n{mensagens_formatadas}\n\n"
                    f"**Respostas:**\n{respostas_formatadas}\n\n"
                )
                await self.aluno_cog.load_demanda_view(interaction,self.usuario_atual)

                return

    async def show_deletar_respostas(self, interaction: discord.Interaction, duvidas):

        duvidas_com_respostas = {
        usuario: [
            dado for dado in lista_duvidas if not dado["dados"].get("visualizada", True)
        ]
        for usuario, lista_duvidas in duvidas.items()
        }
        duvidas_com_respostas = {usuario: lista for usuario, lista in duvidas_com_respostas.items() if lista}

        await interaction.followup.send(
            "⚠️ **ATENÇÃO!**\n\n"
            "🛑 **Somente as dúvidas que NÃO foram visualizadas pelo aluno podem ser editadas.**\n\n"
            "❌ **Caso o usuário já tenha visualizada você não pode mais alterar**\n"
        )

        if not duvidas_com_respostas:
            await interaction.followup.send("Não há respostas para exibir.")
            await self.aluno_cog.load_demanda_view(interaction,self.usuario_atual)
            return
        

        # Lista usuários com dúvidas respondidas
        usuarios_com_respostas = sorted(
            duvidas_com_respostas.keys(),
            key=lambda usuario: duvidas_com_respostas[usuario][0]["dados"]["timestamp_duvida"])

        while True:
            lista_usuarios = "\n".join([f"{i + 1}. {user}" for i, user in enumerate(usuarios_com_respostas)])
            await interaction.followup.send(
                f"Escolha um usuário para deletar as respostas associadas às dúvidas:\n{lista_usuarios}"
            )
            escolha_usuario  = await self.aluno_cog.gerenciar_timeout(interaction, 300)
        
            if escolha_usuario is None:
                return
            escolha_usuario = escolha_usuario.content.strip() 
            
            
            if not escolha_usuario.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue
            
        
            escolha_usuario_index = int(escolha_usuario) - 1

            if escolha_usuario_index < 0 or escolha_usuario_index >= len(usuarios_com_respostas):
                await interaction.followup.send("Escolha inválida. Por favor, tente novamente.")
                continue

            usuario_selecionado = usuarios_com_respostas[escolha_usuario_index]
            duvidas_usuario = duvidas_com_respostas[usuario_selecionado]

                    

            while True:
                lista_titulos = "\n".join([f"{i + 1}. {item['titulo']}" for i, item in enumerate(duvidas_usuario)])

            
                await interaction.followup.send(
                    f"Escolha um título para deletar as respostas:\n{lista_titulos}"
                )

                escolha_titulo  = await self.aluno_cog.gerenciar_timeout(interaction, 300)
        
                if escolha_titulo is None:
                    return
                escolha_titulo = escolha_titulo.content.strip()
                
                
                if not escolha_titulo.isdigit():
                    await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                    continue
            

                escolha_titulo_index = int(escolha_titulo) - 1

                if escolha_titulo_index < 0 or escolha_titulo_index >= len(duvidas_usuario):
                    await interaction.followup.send("Escolha inválida. Por favor, tente novamente.")
                    continue
                
                titulo_selecionado = duvidas_usuario[escolha_titulo_index]
                dados = titulo_selecionado["dados"]
                dados = titulo_selecionado["dados"]

                # Esvazia a lista de respostas diretamente no dicionário
                dados["respostas"] = [] 
                await self.aluno_cog.load_demanda_view(interaction,self.usuario_atual)
                return


    async def show_editar_respostas(self, interaction: discord.Interaction,duvidas):

        # Filtra as dúvidas que possuem respostas
        duvidas_com_respostas = {
        usuario: [
            dado for dado in lista_duvidas if not dado["dados"].get("visualizada", True)
        ]
        for usuario, lista_duvidas in duvidas.items()
        }
        duvidas_com_respostas = {usuario: lista for usuario, lista in duvidas_com_respostas.items() if lista}
        await interaction.followup.send(
            "⚠️ **ATENÇÃO!**\n\n"
            "🛑 **Somente as dúvidas que NÃO foram visualizadas pelo aluno podem ser editadas.**\n\n"
            "❌ **Caso o usuário já tenha visualizada você não pode mais alterar**\n"
        )
    

        if not duvidas_com_respostas:
            await interaction.followup.send("Não há respostas para exibir.")
            await self.aluno_cog.load_demanda_view(interaction,self.usuario_atual)
            return
        
        # Lista usuários com dúvidas respondidas
        usuarios_com_respostas = sorted(
            duvidas_com_respostas.keys(),
            key=lambda usuario: duvidas_com_respostas[usuario][0]["dados"]["timestamp_duvida"])

        while True:
            lista_usuarios = "\n".join([f"{i + 1}. {user}" for i, user in enumerate(usuarios_com_respostas)])
            await interaction.followup.send(
                f"Escolha um usuário para editar as respostas associadas às dúvidas:\n{lista_usuarios}"
            )
            escolha_usuario  = await self.aluno_cog.gerenciar_timeout(interaction, 300)
        
            if escolha_usuario is None:
                return
            escolha_usuario = escolha_usuario.content.strip() 
            
            
            if not escolha_usuario.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue
            
        
            escolha_usuario_index = int(escolha_usuario) - 1

            if escolha_usuario_index < 0 or escolha_usuario_index >= len(usuarios_com_respostas):
                await interaction.followup.send("Escolha inválida. Por favor, tente novamente.")
                continue

            usuario_selecionado = usuarios_com_respostas[escolha_usuario_index]
            duvidas_usuario = duvidas_com_respostas[usuario_selecionado]

            while True:
                lista_titulos = "\n".join([f"{i + 1}. {item['titulo']}" for i, item in enumerate(duvidas_usuario)])

            
                await interaction.followup.send(
                    f"Escolha um título para editar as respostas:\n{lista_titulos}"
                )

                escolha_titulo  = await self.aluno_cog.gerenciar_timeout(interaction, 300)
        
                if escolha_titulo is None:
                    return
                escolha_titulo = escolha_titulo.content.strip()
                
                
                if not escolha_titulo.isdigit():
                    await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                    continue
            

                escolha_titulo_index = int(escolha_titulo) - 1

                if escolha_titulo_index < 0 or escolha_titulo_index >= len(duvidas_usuario):
                    await interaction.followup.send("Escolha inválida. Por favor, tente novamente.")
                    continue
                
                titulo_selecionado = duvidas_usuario[escolha_titulo_index]
                titulo = titulo_selecionado["titulo"]
                dados = titulo_selecionado["dados"]
                mensagens= dados.get("mensagens", [])
                respostas = dados.get("respostas", [])
                dados["timestamp_resposta"]=datetime.now()
                
                mensagens_formatadas = "\n".join(
                [f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."
                respostas_formatadas = "\n".join(
                [f"- {resp}" for resp in respostas]) if respostas else "Nenhuma resposta registrada."

                            
                await interaction.followup.send(
                    f"**Título:** {titulo}\n"
                    f"**Mensagens:**\n{mensagens_formatadas}\n\n"
                    f"**Respostas:**\n{respostas_formatadas}\n\n"
                )

                await interaction.followup.send(f"Pode digitar a resposta que irá substituíla , envie quantas quiser.Para finalizar envie uma única mensagem com 'enviar'")

                
                respostas.clear()

                while True:

                    
                    nova_msg =  await self.aluno_cog.gerenciar_timeout(interaction, 300)
                    
                    if nova_msg is None:
                        return
                    
                    nova_msg=nova_msg.content.strip()

                    if nova_msg.lower() == "enviar":
                        break

                    respostas.append(nova_msg)

                nova_msg_formatadas ="\n".join([f"- {msg}" for msg in respostas]) if respostas else "Nenhuma resposta registrada."

                await interaction.followup.send(
                    f"**Dúvida atualizada com sucesso**\n\n"
                    f"**Título:** {titulo}\n"
                    f"**Mensagens:**\n{mensagens_formatadas}\n\n"
                    f"**Respostas:**\n{nova_msg_formatadas}\n\n"
                )
                await self.aluno_cog.load_demanda_view(interaction,self.usuario_atual)
                return
        

    @select(
        placeholder="Selecione o período para filtrar as dúvidas...",
        options=[
            discord.SelectOption(label="Hoje", value="hoje", description="Dúvidas de hoje", emoji="📅"),
            discord.SelectOption(label="Últimos 7 dias", value="7_dias", description="Dúvidas dos últimos 7 dias", emoji="📆"),
            discord.SelectOption(label="Últimos 30 dias", value="30_dias", description="Dúvidas dos últimos 30 dias", emoji="🗓️"),
            discord.SelectOption(label="Todas", value="todas", description="Todas as dúvidas", emoji="🔍")
        ],
        custom_id="menu_filtro"
    )
    async def menu_filtro(self, interaction: discord.Interaction, select: Select):
        await self.disable_and_update(interaction)

        agora = datetime.now()

        if select.values[0] == "hoje":
            inicio_periodo = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        elif select.values[0] == "7_dias":
            inicio_periodo = agora - timedelta(days=7)
        elif select.values[0] == "30_dias":
            inicio_periodo = agora - timedelta(days=30)
        else:
            inicio_periodo = None  # Para "Todas"
        duvidas_com_respostas = {}
        if inicio_periodo:
           for usuario_name, duvidas in self.duvidas.items():
            duvidas_com_resposta = []
            for dado in duvidas:
                # Usa .get() para acessar 'timestamp_resposta' de forma segura
                timestamp_resposta = dado["dados"].get("timestamp_resposta")
                
                # Verifica se timestamp_resposta existe e se está dentro do período
                if timestamp_resposta and (not inicio_periodo or timestamp_resposta >= inicio_periodo):
                    titulo = dado.get("titulo")
                    # Adiciona a estrutura correta para manter o padrão desejado
                    duvidas_com_resposta.append({
                        "titulo": titulo,
                        "dados": dado["dados"]  # Aqui, apenas adicionamos o conteúdo do "dados" diretamente
                    })
            
            # Ordena as dúvidas com base no timestamp
            if duvidas_com_resposta:
                duvidas_com_resposta.sort(key=lambda d: d["dados"].get("timestamp_duvida", 0))
                duvidas_com_respostas[usuario_name] = duvidas_com_resposta


        else:
            duvidas_com_respostas=self.duvidas
        print(duvidas_com_respostas)


       
        if self.tipo=='editar':
           await self.show_editar_respostas(interaction,duvidas_com_respostas)
        elif self.tipo=='visualizar':
            await self.show_visualizar_respostas(interaction,duvidas_com_respostas)
        elif self.tipo=='deletar':
            await self.show_deletar_respostas(interaction,duvidas_com_respostas)
    

async def setup(bot):
    await bot.add_cog(Coordenador(bot))
