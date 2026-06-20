import discord


class HelpView(discord.ui.View):
    def __init__(self, pages, author, translate):
        super().__init__(timeout=60)
        self.pages = pages
        self.current_page = 0
        self.author = author
        self.translate = translate
        self.update_buttons()

    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    def get_embed(self):
        return self.pages[self.current_page]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(self.translate("button_unauthorized"), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
