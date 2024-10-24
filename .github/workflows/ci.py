import anyio
import dagger


async def test():
    async with dagger.Connection() as client:
        # Get Python image
        python = (
            client.container()
            .from_("python:3.12-slim")
            .with_exec(["pip", "install", "poetry"])
        )

        # Mount source code
        src = client.host().directory(".")

        # Create test container
        test = (
            python
            # Mount source code
            .with_mounted_directory("/app", src)
            # Set working directory
            .with_workdir("/app")
            # Install dependencies
            .with_exec(["poetry", "install", "--no-root"])
            # Install project
            .with_exec(["poetry", "install"])
            # Run tests
            .with_exec(["poetry", "run", "pytest", "tests/", "-v"])
        )

        # Execute the pipeline
        await test.exit_code()


if __name__ == "__main__":
    anyio.run(test)
