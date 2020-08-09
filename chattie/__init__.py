from .chattie import Chattie


def setup(bot):
    bot.add_cog(Chattie(bot))
