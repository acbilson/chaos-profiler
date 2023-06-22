from test import run
from src.profile_operators import profile_func, ProfileRunSettings

if __name__ == "__main__":
    profile_run = profile_func(
        ProfileRunSettings(
            func=run.get_letters_and_numbers,
            func_file_names=[run.letters.__file__, run.numbers.__file__],
        )
    )

    print(str(profile_run))
